"""
CombatEnv: a minimal Gym-style wrapper around CombatEngine, intended as
the actual thing you point an RL trainer at.

Design choices made for training speed / simplicity (documented so you
can tell me which to change):

- Discrete action space per player-turn-step: one action id per
  (card-in-hand-slot, target) pair, plus an END_TURN action.
- Hand slots are padded to MAX_HAND so the action space has fixed size.
- Observation is a flat float vector (see _observe). Swap in a richer
  encoder later without touching CombatEngine.
- Co-op is modeled as two agents acting in sequence within the same
  "player phase" of a turn (player 0 fully acts, ends its sub-turn,
  then player 1 acts) -- simplest possible interleaving. If you want
  simultaneous/alternating single-card actions instead, that's a
  one-function change in step().
"""

from typing import List, Optional, Tuple
import numpy as np

from .entities import Player, seed_content
from .enemies import Enemy
from .cards import Card, CardType, TargetMode, card_id
from .combat import CombatEngine
from .statuses import StatusType, DEBUFF_STATUSES, net_strength, net_dexterity
from .relics import relic_id, TOTAL_RELIC_IDS
from .potions import potion_id, TOTAL_POTION_IDS

MAX_HAND = 10
# Imported from the engine rather than restated, because the two silently
# diverged once already: this was 4 (correct when enemy lineups were fixed
# and the largest was 4), then #23 added mid-combat summoning and nothing
# here was revisited. Phrog Parasite spawns 4 Wrigglers on death and
# Two-Tailed Rat can summon repeatedly, so the engine caps the board at 12 --
# and every enemy past index 3 was invisible in the observation AND
# unreachable through the action space.
MAX_ENEMIES = CombatEngine.MAX_ENEMIES
# STS2 co-op is 1-4 players (asserted in CombatEngine.__init__). The
# observation pads to this so its layout does not depend on party size.
MAX_PLAYERS = 4
# Potion belt: 3 by default, +2 from Potion Belt, so 5 is the real ceiling.
MAX_POTIONS = 5

# --- action space ----------------------------------------------------------
# [0, CARD_ACTIONS)                  play hand slot s at target t
# [CARD_ACTIONS, +POTION_ACTIONS)    drink potion slot s at target t
# last id                            end turn
CARD_ACTIONS = MAX_HAND * MAX_ENEMIES
POTION_ACTIONS = MAX_POTIONS * MAX_ENEMIES
FIRST_POTION_ACTION = CARD_ACTIONS
END_TURN_ACTION = CARD_ACTIONS + POTION_ACTIONS  # sentinel action id

# Per-slot hand features, in this order. The action space indexes hand
# SLOTS, so without these the agent is choosing "slot 3" with no idea what
# is in it -- and the contents change every turn, which makes the mapping
# from action to consequence close to random.
#
# Semantic features rather than a card-identity one-hot: 10 slots x 226
# known printings would be 2260 floats that teach the network nothing
# transferable between, say, Strike and Ultimate Strike. These generalise,
# and anything wanting true identity can take it from hand_card_ids() and
# own an embedding table. Deliberately NOT ordinal-encoding the card id as a
# float here -- id 5 is not "less than" id 200 in any useful sense.
HAND_FEATURE_NAMES = (
    "occupied", "playable", "cost", "is_x_cost",
    "is_attack", "is_skill", "is_power", "is_status", "is_curse",
    "damage", "block", "exhausts", "retain", "ethereal", "upgraded",
)
HAND_FEATURES = len(HAND_FEATURE_NAMES)
PILE_FEATURES = 4          # hand, draw, discard, exhaust counts

# Status channels, per entity. A dense vector over all 44 StatusTypes x 16
# entities would be 704 mostly-zero floats, so this is a curated set --
# several channels FOLD related statuses together, which is also how the
# engine reads them:
#   strength/dexterity/thorns each have a _THIS_TURN and a _LOSS variant;
#   deal_attack_damage and gain_block already use the net value, so the
#   observation shows the same number the rules do.
#   metallicize and plated armor both grant end-of-turn Block via one
#   branch in apply_end_of_turn_gains.
#   evasion groups the "your attack may not land properly" family.
#   restricted groups the "you may not act freely" family.
# `other_debuffs` is a catch-all count so a debuff outside this list is
# still *visible* as something, rather than silently reading as zero.
STATUS_CHANNEL_NAMES = (
    "strength", "dexterity", "vulnerable", "weak", "frail", "poison",
    "intangible", "artifact", "thorns", "plating", "regen", "ritual",
    "vigor", "buffer", "evasion", "restricted", "other_debuffs",
)
STATUS_FEATURES = len(STATUS_CHANNEL_NAMES)

# Statuses folded into a named channel above; anything else that is a debuff
# falls through to `other_debuffs`.
_FOLDED = {
    StatusType.STRENGTH, StatusType.STRENGTH_THIS_TURN,
    StatusType.STRENGTH_LOSS, StatusType.STRENGTH_LOSS_THIS_TURN,
    StatusType.DEXTERITY, StatusType.DEXTERITY_THIS_TURN,
    StatusType.DEXTERITY_LOSS, StatusType.DEXTERITY_LOSS_THIS_TURN,
    StatusType.VULNERABLE, StatusType.WEAK, StatusType.FRAIL,
    StatusType.POISON, StatusType.INTANGIBLE, StatusType.ARTIFACT,
    StatusType.THORNS, StatusType.THORNS_THIS_TURN,
    StatusType.METALLICIZE, StatusType.PLATED_ARMOR, StatusType.REGEN,
    StatusType.RITUAL, StatusType.VIGOR, StatusType.BUFFER,
    StatusType.SLIPPERY, StatusType.SOAR, StatusType.FLUTTER,
    StatusType.RINGING, StatusType.SMOGGY, StatusType.HEX,
    StatusType.TANGLED, StatusType.DOWNGRADED,
}

ENTITY_FEATURES = 3 + STATUS_FEATURES     # hp/intent-or-energy/block + statuses
# Shared all-zero row for the (very common) statusless entity, returned by
# _status_features instead of building a fresh list per empty slot per step.
# MUST NOT BE MUTATED: it is one object handed out repeatedly, so writing to
# a returned row would change every empty slot at once. Its only caller does
# `feats += ...`, which copies out of it rather than into it.
_NO_STATUSES = [0.0] * STATUS_FEATURES
RELIC_FEATURES = TOTAL_RELIC_IDS          # multi-hot, static within a combat
POTION_FEATURES = MAX_POTIONS * TOTAL_POTION_IDS

# Section offsets, exported so a trainer (or a test) can slice the vector
# without recomputing the arithmetic and drifting from it.
OBS_OFFSETS = {}
_off = 0
for _name, _width in (
    ("players", MAX_PLAYERS * ENTITY_FEATURES),
    ("enemies", MAX_ENEMIES * ENTITY_FEATURES),
    ("relics", RELIC_FEATURES),
    ("potions", POTION_FEATURES),
    ("piles", PILE_FEATURES),
    ("hand", MAX_HAND * HAND_FEATURES),
):
    OBS_OFFSETS[_name] = (_off, _off + _width)
    _off += _width
OBS_SIZE = _off
del _off, _name, _width


class CombatEnv:
    def __init__(self, make_players, make_enemies, seed: Optional[int] = None,
                  max_turns: Optional[int] = 200):
        """
        make_players: Callable[[], List[Player]]  -- factory so reset() gets fresh decks
        make_enemies: Callable[[], List[Enemy]]
        seed:         pins BOTH the engine and the content rng; see reset()
        max_turns:    truncation cap in engine turns, or None to disable
        """
        self._make_players = make_players
        self._make_enemies = make_enemies
        self.seed = seed
        # Truncation cap, in ENGINE TURNS (not steps -- a turn is many steps).
        # An unbounded episode does not fail loudly, it hangs the rollout that
        # is collecting it, so a trainer wants a bound even if nothing ever
        # reaches it. 200 is ~14x the worst turn count seen in real play (14,
        # random policy) and >3x bench.py's own MAX_TURNS=60, so it cannot
        # fire by accident -- it exists to bound the pathological case, not to
        # shape episodes. Pass None to disable.
        self.max_turns = max_turns
        self._truncated = False
        self.engine: Optional[CombatEngine] = None
        self.active_player_idx = 0  # whose sub-turn it is within the player phase
        # Scratch buffer that _observe fills in place; see its docstring.
        # Allocated here rather than in reset() so it exists even if a caller
        # observes before resetting.
        self._obs = np.zeros(OBS_SIZE, dtype=np.float32)

    # ---------- gym-like API ----------
    def reset(self, seed: Optional[int] = None) -> np.ndarray:
        """Start a fresh episode.

        `seed` is optional and additive: omit it and the env behaves exactly
        as it always has, replaying self.seed every reset. Pass one and BOTH
        sources of randomness are pinned to it -- the engine (deck shuffles,
        enemy move rng) and the content rng (the HP a factory rolls).

        Both have to be pinned or neither is worth pinning. The engine seed
        alone was never enough: an enemy's HP is rolled inside make_nibbit()
        BEFORE any engine exists, off a module rng nothing seeded, so
        reset()ing the same env twice fought a different Nibbit each time.
        That is why seeding happens here, in the driver, ahead of the
        factories -- see enemies.seed_content()."""
        episode_seed = self.seed if seed is None else seed
        # Guarded rather than unconditional: seed_content(None) would reseed
        # from system entropy on every reset, where an unseeded env should
        # just keep drawing from the stream it already had.
        if episode_seed is not None:
            seed_content(episode_seed)
        players = self._make_players()
        enemies = self._make_enemies()
        self.engine = CombatEngine(players, enemies, seed=episode_seed)
        self.engine.start_player_turn()
        self.active_player_idx = 0
        self._truncated = False
        return self._observe()

    def action_space_size(self) -> int:
        return END_TURN_ACTION + 1

    def observation_space_size(self) -> int:
        """Companion to action_space_size, so a trainer can size its input
        layer without reverse-engineering _observe."""
        return OBS_SIZE

    def legal_action_mask(self) -> np.ndarray:
        """Which actions the engine will actually accept right now.

        Legality comes from CombatEngine.playable_cards, NOT from a local
        copy of the rules. This used to re-derive "can I afford it?" here,
        which meant every play gate added to the engine afterwards was
        invisible to the agent: Clash's play condition and the Sloth/
        Normality play caps both marked legal, then got refused by
        play_card. A masked agent would pick them, eat the illegal-action
        penalty and waste the step. This function now only decides
        TARGETING; whether a card may be played at all is the engine's
        answer."""
        mask = np.zeros(self.action_space_size(), dtype=np.float32)
        mask[END_TURN_ACTION] = 1.0
        player = self._current_player()
        if player is None:
            return mask
        hand = player.hand[:MAX_HAND]
        # Identity, not equality: Card sets eq=False precisely so two cards
        # with the same numbers are still distinct instances.
        playable = {id(c) for c in self.engine.playable_cards(player)}
        alive_idx = self._alive_enemy_indices()
        allies = self._allies_in_obs_order()
        for slot, card in enumerate(hand):
            if id(card) not in playable:
                continue
            if card.target == TargetMode.SINGLE_ENEMY:
                base = slot * MAX_ENEMIES
                for t_idx in alive_idx:
                    mask[base + t_idx] = 1.0
            elif card.target == TargetMode.ALLY:
                # t_idx counts over the OBSERVATION's ally order, so ally
                # action k always names the teammate at player-slot k+1.
                base = slot * MAX_ENEMIES
                for t_idx, mate in enumerate(allies[:MAX_ENEMIES]):
                    if mate.alive:
                        mask[base + t_idx] = 1.0
            else:
                # SELF / ALL_ENEMIES / SELF_OR_ALLY (unexercised): target
                # slot 0 as a dummy, resolved server-side in play_card().
                mask[slot * MAX_ENEMIES + 0] = 1.0

        # Potions. All 52 are modelled and CombatEngine.use_potion works, but
        # there was no action id for them, so an agent simply could not drink
        # one -- which is why bench.py needed its own maybe_use_potion, and
        # why an early benchmark bot collected potions and died holding them.
        for slot, potion in enumerate(player.potions[:MAX_POTIONS]):
            base = FIRST_POTION_ACTION + slot * MAX_ENEMIES
            if potion.target == "enemy":
                for t_idx in alive_idx:
                    mask[base + t_idx] = 1.0
            else:
                # "self" / "all_enemies" / "none" pick their own targets.
                mask[base] = 1.0
        return mask

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, dict]:
        assert self.engine is not None, "call reset() first"
        engine = self.engine
        # ABSORBING TERMINAL STATE. Stepping a finished episode used to fall
        # through and re-award the +10/-10 terminal bonus EVERY time, so a
        # rollout loop that ignored `done` could farm unbounded reward from a
        # won fight -- silent, because nothing crashes and every standard
        # trainer happens to respect `done`. A finished episode now returns
        # zero reward and changes nothing.
        if engine.is_over or self._truncated:
            return (self._observe(), 0.0, True,
                    {"log_tail": engine.log[-3:], "truncated": self._truncated,
                     "absorbing": True})

        player = self._current_player()
        reward = 0.0

        if action == END_TURN_ACTION or player is None:
            self._advance_sub_turn()
        elif action >= FIRST_POTION_ACTION:
            offset = action - FIRST_POTION_ACTION
            slot, t_idx = offset // MAX_ENEMIES, offset % MAX_ENEMIES
            belt = player.potions[:MAX_POTIONS]
            if slot >= len(belt):
                reward -= 1.0
            else:
                potion = belt[slot]
                target = self._enemy_at(t_idx) if potion.target == "enemy" else None
                pre_enemy_hp = sum(e.hp for e in engine.enemies)
                if not engine.use_potion(player, potion, target=target):
                    reward -= 1.0
                else:
                    post_enemy_hp = sum(e.hp for e in engine.enemies)
                    reward += 0.01 * (pre_enemy_hp - post_enemy_hp)
        else:
            slot = action // MAX_ENEMIES
            t_idx = action % MAX_ENEMIES
            hand = player.hand[:MAX_HAND]
            if slot >= len(hand):
                reward -= 1.0  # illegal action penalty
            else:
                card = hand[slot]
                target = None
                ally = None
                if card.target == TargetMode.SINGLE_ENEMY:
                    target = self._enemy_at(t_idx)
                elif card.target == TargetMode.ALLY:
                    ally = self._ally_at(t_idx)

                pre_enemy_hp = sum(e.hp for e in engine.enemies)
                ok = engine.play_card(player, card, target=target, ally_target=ally)
                if not ok:
                    reward -= 1.0
                else:
                    post_enemy_hp = sum(e.hp for e in engine.enemies)
                    reward += 0.01 * (pre_enemy_hp - post_enemy_hp)  # shaped reward: dmg dealt

        done = engine.is_over
        if done:
            reward += 10.0 if engine.victory else -10.0
        elif self.max_turns is not None and engine.turn_number > self.max_turns:
            # Truncation is NOT termination: the fight was cut short, so it
            # earns neither the victory bonus nor the defeat penalty. A
            # bootstrapping learner needs to tell the two apart, which is
            # what info["truncated"] is for (and what the Gymnasium wrapper
            # turns into a real `truncated` flag).
            self._truncated = True
            done = True

        return (self._observe(), reward, done,
                {"log_tail": engine.log[-3:], "truncated": self._truncated})

    # ---------- egocentric framing ----------
    def _obs_player_order(self) -> List[Player]:
        """Players as the observation shows them: the ACTING player first,
        then the rest in seat order, wrapping around.

        The observation used to list players by seat, which meant a shared
        co-op policy could not tell its own HP from a teammate's -- slot 0
        was P0 whether P0 was the one acting or not. Since every other
        egocentric section (relics, potions, piles, hand) already described
        the acting player, the vector was also internally inconsistent: the
        hand shown belonged to one player while the HP at slot 0 could belong
        to another.

        Rotating is enough on its own; no "this is me" flag is needed,
        because slot 0 IS me by construction. It is also cheaper than a flag,
        which would have widened every entity slot and moved every offset.

        Wrapping rather than sorting keeps relative seating stable: the
        teammate at slot 1 is always the next seat round, so a policy can
        learn "my left-hand neighbour" rather than re-deriving who is who.

        Falls back to seat order when there is no acting player -- the index
        runs past the party once every player has ended their sub-turn, and
        after a defeat it stays there."""
        players = self.engine.players
        idx = self.active_player_idx
        if idx >= len(players):
            idx = 0
        return players[idx:] + players[:idx]

    def _allies_in_obs_order(self) -> List[Player]:
        """The non-acting players, in the order the observation shows them.

        This is what ally target indices count over, so **ally action k names
        the player at observation player-slot k+1**. Using the engine's
        other_players() here instead would re-sort them by seat and break
        that correspondence the moment the acting player is not P0 -- with
        three players and P1 acting, the observation shows [P1, P2, P0] while
        other_players(P1) returns [P0, P2], so slot 1 and ally 0 would name
        different teammates.

        Dead allies keep their slot rather than being filtered out, so the
        mapping does not shift when someone goes down; legality is the
        mask's job, not the ordering's."""
        return self._obs_player_order()[1:]

    # ---------- action-index -> game-object resolution ----------
    def _ally_at(self, t_idx: int) -> Optional[Player]:
        """The ally an action's target index names, with the same
        first-living fallback _enemy_at uses for the same reasons."""
        allies = self._allies_in_obs_order()
        if t_idx < len(allies) and allies[t_idx].alive:
            return allies[t_idx]
        for a in allies:
            if a.alive:
                return a
        return None

    def _alive_enemy_indices(self) -> List[int]:
        """Target slots that currently point at a living enemy.

        Computed once per mask instead of re-scanning the board for every
        card and every potion, which is what the two loops in
        legal_action_mask used to do."""
        return [i for i, e in enumerate(self.engine.enemies[:MAX_ENEMIES])
                if e.alive]

    def _enemy_at(self, t_idx: int) -> Optional[Enemy]:
        """The enemy an action's target index names, with a fallback.

        A masked agent always picks a live target, but step() must stay
        total: nothing stops a caller passing an unmasked action, and an
        index can also go stale between mask and step if the target dies to
        a Thorns or Steam Eruption tick in between. Falling back to the
        first living enemy matches what play_card does with a dead target,
        so the two cannot disagree.

        This was written out three times -- the card branch of step(), the
        potion branch, and again in legal_action_mask -- each version
        building a full list of living enemies just to take element zero."""
        enemies = self.engine.enemies
        if t_idx < len(enemies) and enemies[t_idx].alive:
            return enemies[t_idx]
        for e in enemies[:MAX_ENEMIES]:
            if e.alive:
                return e
        return None

    # ---------- internal turn choreography ----------
    def _current_player(self) -> Optional[Player]:
        if self.engine is None:
            return None
        alive_players = [p for p in self.engine.players if p.alive]
        if self.active_player_idx >= len(self.engine.players):
            return None
        p = self.engine.players[self.active_player_idx]
        return p if p.alive else None

    def _advance_sub_turn(self):
        engine = self.engine
        self.active_player_idx += 1
        if self.active_player_idx >= len(engine.players):
            # all players have ended their sub-turn -> resolve full turn
            engine.end_player_turn()
            if not engine.is_over:
                engine.run_enemy_turn()
            if not engine.is_over:
                engine.start_player_turn()
                self.active_player_idx = 0

    # ---------- observation ----------
    def _observe(self) -> np.ndarray:
        """Fixed layout: MAX_PLAYERS player triples, then MAX_ENEMIES enemy
        triples, always in that order and always that many.

        EGOCENTRIC: player slot 0 is always the acting player, teammates
        follow in wrapped seat order, and ally action k names slot k+1. See
        _obs_player_order() for why, and _allies_in_obs_order() for the
        targeting half.

        The previous version padded players only up to 2 and then relied on
        a single trailing pad-to-total loop. The total length came out right
        (18) for every party size, so nothing ever looked broken -- but with
        3-4 players the EXTRA players' features occupied the slots a decoder
        would read as enemies, and the enemies shifted along behind them. A
        silent misalignment rather than a crash, which is why it survived.
        Padding each section to its own fixed width is what actually fixes
        it; a correct total is not the same as a correct layout.

        Sections, in order and with widths in OBS_OFFSETS: players, enemies,
        relics, potions, pile counts, hand.

        WRITTEN INTO A REUSED BUFFER, not built as a list. The old version
        assembled 817 Python floats and handed them to np.array() every step,
        which made np.array the single hottest line in the whole env profile
        and _observe about 43% of a step. Most of that work produced ZEROS:
        240 floats of enemy padding, a 260-float potion one-hot with at most
        five bits set, an 83-float relic vector with two or three.

        So the buffer is zeroed once per call with a single vectorised fill
        and only the non-zero values are written. That is exactly equivalent
        because every unwritten position in the old version was a pad zero --
        which is also why a dead enemy, an empty status set and an unused hand
        slot are now simply SKIPPED rather than filled with zeros by hand.

        The return is a COPY, deliberately. A trainer that stores observations
        in a replay buffer must not have them mutate under it on the next
        step. The copy is ~1us against the ~31us the list-building cost, so
        the safe API is still far cheaper than what it replaced."""
        engine = self.engine
        buf = self._obs
        buf.fill(0.0)

        i = OBS_OFFSETS["players"][0]
        for p in self._obs_player_order()[:MAX_PLAYERS]:
            buf[i] = p.hp / max(1, p.max_hp)
            buf[i + 1] = p.block / 50.0
            buf[i + 2] = p.energy / max(1, p.max_energy)
            st = self._status_features(p)
            # Identity check against the shared all-zero row: the buffer is
            # already zero there, so the common statusless case writes nothing.
            if st is not _NO_STATUSES:
                buf[i + 3:i + ENTITY_FEATURES] = st
            i += ENTITY_FEATURES

        i = OBS_OFFSETS["enemies"][0]
        for e in engine.enemies[:MAX_ENEMIES]:
            if e.alive:
                intent_dmg = e.current_move.damage if e.current_move else 0
                buf[i] = e.hp / max(1, e.max_hp)
                buf[i + 1] = intent_dmg / 20.0
                buf[i + 2] = e.block / 50.0
                st = self._status_features(e)
                if st is not _NO_STATUSES:
                    buf[i + 3:i + ENTITY_FEATURES] = st
            i += ENTITY_FEATURES

        player = self._current_player()
        if player is None:
            # Everything past the entity sections stays zero, exactly as the
            # explicit zero-padding used to make it.
            return buf.copy()

        # Relics: multi-hot. Several change what correct play looks like (Ice
        # Cream conserves energy, Sturdy Clamp keeps Block, Red Skull below
        # half HP), so an agent that cannot see them cannot learn to exploit
        # them. Per CURRENT player, not per combat -- in co-op each teammate
        # has their own, so this cannot be hoisted out to reset().
        base = OBS_OFFSETS["relics"][0]
        for r in player.relics:
            rid = relic_id(r)
            if rid >= 0:
                buf[base + rid] = 1.0

        # Potions: a per-slot ONE-HOT, unlike the hand's semantic features.
        # The opposite choice from cards, on purpose. A card has structured,
        # generalisable attributes (cost, type, damage, block, keywords) so
        # features beat identity; a potion is an opaque effect callable with
        # no comparable structure, so identity is all there is to encode.
        # The action space indexes potion SLOTS, so this has to be per slot
        # rather than a single "what do I hold" multi-hot.
        base = OBS_OFFSETS["potions"][0]
        for s, pot in enumerate(player.potions[:MAX_POTIONS]):
            pid = potion_id(pot)
            if pid >= 0:
                buf[base + s * TOTAL_POTION_IDS + pid] = 1.0

        base = OBS_OFFSETS["piles"][0]
        buf[base] = len(player.hand) / 10.0
        buf[base + 1] = len(player.draw_pile) / 30.0
        buf[base + 2] = len(player.discard_pile) / 30.0
        buf[base + 3] = len(player.exhaust_pile) / 30.0

        # Legality comes from the engine, same single source as the action
        # mask -- so "playable" in the observation and "legal" in the mask
        # can never disagree.
        i = OBS_OFFSETS["hand"][0]
        playable = {id(c) for c in engine.playable_cards(player)}
        for card in player.hand[:MAX_HAND]:
            buf[i:i + HAND_FEATURES] = self._card_features(
                card, player, id(card) in playable)
            i += HAND_FEATURES
        return buf.copy()

    @staticmethod
    def _status_features(entity) -> List[float]:
        """One entity's status channels, in STATUS_CHANNEL_NAMES order.

        Scaled by /10 rather than /1: stacks are usually single digits, and
        an unbounded raw count would swamp the 0-1 features around it.
        Strength and Dexterity can legitimately go negative (Shrink, Dark
        Shackles), and that sign is kept -- clamping it at zero would hide
        the whole point of those cards.

        TWO SPEED CHANGES, both worth knowing about because this is the
        hottest function in the env -- _observe runs it for 16 entity slots
        every single step:

        1. The empty-dict early return. Most entity slots are empty most of
           the time (unused player/enemy slots, and anything with no statuses
           yet), and that case now costs a dict truth-test instead of ~25
           lookups. This is where essentially all of the gain came from.
        2. `g = st.get` instead of `entity.get_status(...)`. Same lookup,
           minus a method call per status. `.get` needs an explicit `, 0`
           default where get_status supplied one itself -- that is the only
           reason for the noise at the end of each call.

        Deliberately NOT done: aliasing `StatusType` to a one-letter name.
        Measured at 4.68us vs 4.65us -- it buys nothing and costs a reader
        having to hold "S" in their head through 25 lines.

        ONE SPEED CHANGE GIVEN BACK, knowingly: strength and dexterity are no
        longer summed inline here, they call statuses.net_strength /
        net_dexterity -- the same helpers deal_attack_damage and gain_block
        use. That costs a function call, measured at 1.00x for an empty or
        typical entity (the early return dominates) and 0.93x for one
        carrying six statuses. It is worth it: this vector is what the agent
        LEARNS FROM, and an observation that computed Strength even slightly
        differently from the rules would be teaching a number the engine does
        not use. The same trade made the engine side 1.6-1.8x FASTER, since
        those two call sites dropped four get_status() method calls each."""
        st = entity.statuses
        if not st:
            return _NO_STATUSES
        g = st.get
        # Shared with the engine rather than restated. These two were the
        # third copy of a four-term formula, and an observation that computes
        # Strength differently from deal_attack_damage is worse than useless:
        # it teaches the agent a number the rules do not use.
        strength = net_strength(st)
        dexterity = net_dexterity(st)
        thorns = g(StatusType.THORNS, 0) + g(StatusType.THORNS_THIS_TURN, 0)
        plating = g(StatusType.METALLICIZE, 0) + g(StatusType.PLATED_ARMOR, 0)
        evasion = (g(StatusType.SLIPPERY, 0) + g(StatusType.SOAR, 0)
                   + g(StatusType.FLUTTER, 0))
        restricted = (g(StatusType.RINGING, 0) + g(StatusType.SMOGGY, 0)
                      + g(StatusType.HEX, 0) + g(StatusType.TANGLED, 0)
                      + g(StatusType.DOWNGRADED, 0))
        other = sum(n for s, n in st.items()
                    if n > 0 and s in DEBUFF_STATUSES and s not in _FOLDED)
        return [v / 10.0 for v in (
            strength, dexterity, g(StatusType.VULNERABLE, 0), g(StatusType.WEAK, 0),
            g(StatusType.FRAIL, 0), g(StatusType.POISON, 0),
            g(StatusType.INTANGIBLE, 0), g(StatusType.ARTIFACT, 0),
            thorns, plating, g(StatusType.REGEN, 0), g(StatusType.RITUAL, 0),
            g(StatusType.VIGOR, 0), g(StatusType.BUFFER, 0),
            evasion, restricted, other,
        )]

    @staticmethod
    def _card_features(card: Card, player: Player, playable: bool) -> List[float]:
        """One hand slot, in HAND_FEATURE_NAMES order."""
        cost = card.current_cost(player)
        is_x = 1.0 if cost == "X" else 0.0
        # Unplayable cards carry the UNPLAYABLE sentinel (999) as their cost;
        # clamped so one Wound does not dominate the whole input scale.
        cost_f = 0.0 if cost == "X" else min(int(cost), 6) / 6.0
        t = card.card_type
        return [
            1.0,
            1.0 if playable else 0.0,
            cost_f,
            is_x,
            1.0 if t == CardType.ATTACK else 0.0,
            1.0 if t == CardType.SKILL else 0.0,
            1.0 if t == CardType.POWER else 0.0,
            1.0 if t == CardType.STATUS else 0.0,
            1.0 if t == CardType.CURSE else 0.0,
            card.val("damage") / 20.0,
            card.val("block") / 20.0,
            1.0 if card.exhausts_now() else 0.0,
            1.0 if card.retains_now() else 0.0,
            1.0 if card.is_ethereal() else 0.0,
            1.0 if card.upgraded else 0.0,
        ]

    def render(self) -> str:
        """Compact text board. RETURNS a string rather than printing it, so a
        caller can log it, diff it in a test, or ignore it -- which is also
        what gymnasium's render_mode="ansi" means. play.py owns the pretty
        version; this is for debugging a rollout."""
        engine = self.engine
        if engine is None:
            return "(not reset)"
        lines = []
        for p in engine.players:
            lines.append("{}: {}/{} hp, {} block, {} energy".format(
                p.name, p.hp, p.max_hp, p.block, p.energy))
        for e in engine.enemies:
            if e.alive:
                intent = e.current_move.name if e.current_move else "?"
                lines.append("  {}: {}/{} hp, intent {}".format(
                    e.name, e.hp, e.max_hp, intent))
        return "\n".join(lines)

    def close(self):
        """Nothing to release -- no sockets, files or processes. Present so
        the env satisfies the interface a trainer expects to be able to call
        in a `finally`."""
        return None

    def hand_card_ids(self) -> np.ndarray:
        """Stable card id per hand slot, -1 for an empty slot.

        Kept OUT of the float observation on purpose: a card id is nominal,
        not ordinal, so feeding it as a scaled float would tell a network
        that card 5 is "less than" card 200. This is the hook for a trainer
        that wants a real embedding table -- index it with these, and
        concatenate the result onto _observe()'s vector."""
        ids = np.full(MAX_HAND, -1, dtype=np.int64)
        player = self._current_player()
        if player is None:
            return ids
        for i, card in enumerate(player.hand[:MAX_HAND]):
            ids[i] = card_id(card)
        return ids


# ---------------------------------------------------------------------------
# Gymnasium adapter
#
# CombatEnv deliberately keeps the OLD gym API -- `reset() -> obs` and
# `step() -> (obs, reward, done, info)` -- because play.py, demo.py, bench.py,
# testing/tools/ and the test suite all drive it directly, and none want a
# 5-tuple. Modern libraries (Gymnasium, Stable-Baselines3) require the new
# one, so the translation lives here rather than churning every caller.
#
# gymnasium is an OPTIONAL dependency. The project itself needs only numpy.
# When gymnasium is importable this subclasses gymnasium.Env and publishes
# real spaces, which is what SB3's isinstance checks want; when it is not,
# the same class still works standalone so it stays testable on a bare
# install.
# ---------------------------------------------------------------------------

try:                                    # pragma: no cover - import shim
    import gymnasium as _gym
except ImportError:                     # pragma: no cover
    try:
        import gym as _gym
    except ImportError:
        _gym = None

_GymBase = _gym.Env if _gym is not None else object


class GymnasiumEnv(_GymBase):
    """Gymnasium-style 5-tuple view of CombatEnv.

        from .env import GymnasiumEnv
        env = GymnasiumEnv(make_players, make_enemies, seed=0)
        obs, info = env.reset()
        obs, reward, terminated, truncated, info = env.step(action)

    TERMINATED vs TRUNCATED is the whole reason this is not a two-line lambda.
    A fight that was won or lost is `terminated` and its value bootstraps from
    the terminal reward; a fight cut off by the turn cap is `truncated` and
    the learner must bootstrap from the value function instead. Collapsing
    them -- which the old `done` flag did -- teaches the agent that hitting
    the cap is worth whatever the terminal bonus was.

    `action_masks()` is named for sb3-contrib's MaskablePPO, which looks up
    exactly that method. Given how much of this env's correctness rests on
    the mask agreeing with the engine, masked PPO is the natural fit.
    """

    metadata = {"render_modes": ["ansi"]}

    def __init__(self, make_players, make_enemies, seed=None, max_turns=200,
                  render_mode=None):
        self.env = CombatEnv(make_players, make_enemies, seed=seed,
                             max_turns=max_turns)
        self.render_mode = render_mode
        if _gym is not None:
            self.observation_space = _gym.spaces.Box(
                low=-np.inf, high=np.inf, shape=(OBS_SIZE,), dtype=np.float32)
            self.action_space = _gym.spaces.Discrete(END_TURN_ACTION + 1)
        else:
            self.observation_space = None
            self.action_space = None

    # ---- Gymnasium API ----
    def reset(self, seed=None, options=None):
        obs = self.env.reset(seed=seed)
        return obs, {"action_mask": self.env.legal_action_mask()}

    def step(self, action):
        obs, reward, done, info = self.env.step(int(action))
        truncated = bool(info.get("truncated", False))
        # `done` is True for both outcomes, so terminated is what is left
        # once truncation is accounted for.
        terminated = bool(done and not truncated)
        info = dict(info)
        info["action_mask"] = self.env.legal_action_mask()
        return obs, float(reward), terminated, truncated, info

    # Explicit rather than left to __getattr__: gymnasium.Env defines both as
    # real methods, so normal attribute lookup succeeds on the base class and
    # __getattr__ never fires. The implementation stays in one place.
    def render(self):
        return self.env.render()

    def close(self):
        return self.env.close()

    # ---- masking ----
    def action_masks(self):
        """Boolean mask, the name and dtype sb3-contrib expects."""
        return self.env.legal_action_mask().astype(bool)

    # Anything not translated above belongs to CombatEnv unchanged
    # (hand_card_ids, observation_space_size, OBS_OFFSETS slicing, ...).
    def __getattr__(self, name):
        return getattr(self.env, name)
