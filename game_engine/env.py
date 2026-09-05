"""CombatEnv: a minimal Gym-style wrapper around CombatEngine, intended as the actual thing you..."""

from typing import List, Optional, Tuple
import numpy as np

from .entities import Player, seed_content
from .enemies import Enemy
from .cards import Card, CardType, TargetMode, card_id
from .combat import CombatEngine
from .statuses import StatusType, DEBUFF_STATUSES, net_strength, net_dexterity
from .observe import ALLY_FEATURES, party_summary

MAX_HAND = 10
MAX_ENEMIES = CombatEngine.MAX_ENEMIES
MAX_PLAYERS = 4
MAX_POTIONS = 5

MAX_ALLY_TARGETS = MAX_PLAYERS
# Potions are OUT of both the action space and the observation. Cutting one
# without the other would leave an agent able to drink what it cannot see,
# which is worse than either extreme.
CARD_ENEMY_ACTIONS = MAX_HAND * MAX_ENEMIES
CARD_ALLY_ACTIONS = MAX_HAND * MAX_ALLY_TARGETS
FIRST_CARD_ALLY_ACTION = CARD_ENEMY_ACTIONS
END_TURN_ACTION = FIRST_CARD_ALLY_ACTION + CARD_ALLY_ACTIONS

HAND_FEATURE_NAMES = (
    "occupied", "playable", "cost", "is_x_cost",
    "is_attack", "is_skill", "is_power", "is_status", "is_curse",
    "damage", "block", "exhausts", "retain", "ethereal", "upgraded",
    "targets_enemy", "targets_all_enemies", "targets_self",
    "targets_ally", "targets_self_or_ally",
)
HAND_FEATURES = len(HAND_FEATURE_NAMES)

# Piles by composition, not just size: a bare count cannot answer "how many
# Defends are left" or "is there enough damage in the deck to finish this".
PILE_NAMES = ("hand", "draw", "discard", "exhaust")
PILE_FEATURE_NAMES = ("count", "attacks", "skills", "powers", "statuses",
                      "curses", "damage", "block")
PILE_FEATURES = len(PILE_NAMES) * len(PILE_FEATURE_NAMES)

STATUS_CHANNEL_NAMES = (
    "strength", "dexterity", "vulnerable", "weak", "frail", "poison",
    "intangible", "artifact", "thorns", "plating", "regen", "ritual",
    "vigor", "buffer", "evasion", "restricted", "other_debuffs",
)
STATUS_FEATURES = len(STATUS_CHANNEL_NAMES)

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

ENTITY_FEATURES = 3 + STATUS_FEATURES
_NO_STATUSES = [0.0] * STATUS_FEATURES

OBS_OFFSETS = {}
_off = 0
for _name, _width in (
    ("players", MAX_PLAYERS * ENTITY_FEATURES),
    ("enemies", MAX_ENEMIES * ENTITY_FEATURES),
    ("piles", PILE_FEATURES),
    ("hand", MAX_HAND * HAND_FEATURES),
    # Teammates as capability COUNTS, not raw hands -- see observe.py.
    # Egocentric, matching `players` rows 1..3.
    ("ally_summary", (MAX_PLAYERS - 1) * ALLY_FEATURES),
):
    OBS_OFFSETS[_name] = (_off, _off + _width)
    _off += _width
OBS_SIZE = _off
del _off, _name, _width


class CombatEnv:
    def __init__(self, make_players, make_enemies, seed: Optional[int] = None,
                  max_turns: Optional[int] = 200):
        """make_players: Callable[[], List[Player]] -- factory so reset() gets fresh decks make_enemies..."""
        self._make_players = make_players
        self._make_enemies = make_enemies
        self.seed = seed
        self.max_turns = max_turns
        self._truncated = False
        self.engine: Optional[CombatEngine] = None
        self.active_player_idx = 0
        self._obs = np.zeros(OBS_SIZE, dtype=np.float32)

    def reset(self, seed: Optional[int] = None) -> np.ndarray:
        """Start a fresh episode."""
        episode_seed = self.seed if seed is None else seed
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
        """Companion to action_space_size, so a trainer can size its input layer without..."""
        return OBS_SIZE

    def legal_action_mask(self) -> np.ndarray:
        """Which actions the engine will actually accept right now."""
        mask = np.zeros(self.action_space_size(), dtype=np.float32)
        mask[END_TURN_ACTION] = 1.0
        player = self._current_player()
        if player is None:
            return mask
        hand = player.hand[:MAX_HAND]
        playable = {id(c) for c in self.engine.playable_cards(player)}
        alive_idx = self._alive_enemy_indices()
        seats = self._obs_player_order()[:MAX_ALLY_TARGETS]
        for slot, card in enumerate(hand):
            if id(card) not in playable:
                continue
            if card.target == TargetMode.SINGLE_ENEMY:
                base = slot * MAX_ENEMIES
                for t_idx in alive_idx:
                    mask[base + t_idx] = 1.0
            elif card.target in (TargetMode.ALLY, TargetMode.SELF_OR_ALLY):
                base = FIRST_CARD_ALLY_ACTION + slot * MAX_ALLY_TARGETS
                for t_idx, mate in enumerate(seats):
                    if not mate.alive:
                        continue
                    if t_idx == 0 and card.target == TargetMode.ALLY:
                        continue
                    mask[base + t_idx] = 1.0
            else:
                mask[slot * MAX_ENEMIES + 0] = 1.0

        return mask

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, dict]:
        assert self.engine is not None, "call reset() first"
        engine = self.engine
        if engine.is_over or self._truncated:
            return (self._observe(), 0.0, True,
                    {"log_tail": engine.log[-3:], "truncated": self._truncated,
                     "absorbing": True})

        player = self._current_player()
        reward = 0.0

        if action == END_TURN_ACTION or player is None:
            self._advance_sub_turn()
        else:
            if action >= FIRST_CARD_ALLY_ACTION:
                offset = action - FIRST_CARD_ALLY_ACTION
                slot, t_idx = divmod(offset, MAX_ALLY_TARGETS)
                at_player = True
            else:
                slot, t_idx = divmod(action, MAX_ENEMIES)
                at_player = False
            hand = player.hand[:MAX_HAND]
            if slot >= len(hand):
                reward -= 1.0
            else:
                card = hand[slot]
                target = None
                ally = None
                if card.target == TargetMode.SINGLE_ENEMY:
                    target = self._enemy_at(t_idx)
                elif at_player and card.target in (TargetMode.ALLY,
                                                   TargetMode.SELF_OR_ALLY):
                    ally = self._player_at(t_idx)
                    if ally is player:
                        ally = None

                pre_enemy_hp = sum(e.hp for e in engine.enemies)
                ok = engine.play_card(player, card, target=target, ally_target=ally)
                if not ok:
                    reward -= 1.0
                else:
                    post_enemy_hp = sum(e.hp for e in engine.enemies)
                    reward += 0.01 * (pre_enemy_hp - post_enemy_hp)

        done = engine.is_over
        if done:
            reward += 10.0 if engine.victory else -10.0
        elif self.max_turns is not None and engine.turn_number > self.max_turns:
            self._truncated = True
            done = True

        return (self._observe(), reward, done,
                {"log_tail": engine.log[-3:], "truncated": self._truncated})

    def _obs_player_order(self) -> List[Player]:
        """Players as the observation shows them: the ACTING player first, then the rest in seat order..."""
        players = self.engine.players
        idx = self.active_player_idx
        if idx >= len(players):
            idx = 0
        return players[idx:] + players[:idx]

    def _allies_in_obs_order(self) -> List[Player]:
        """The non-acting players, in the order the observation shows them."""
        return self._obs_player_order()[1:]

    def _player_at(self, t_idx: int) -> Optional[Player]:
        """The player a player-target index names."""
        seats = self._obs_player_order()
        if t_idx < len(seats) and seats[t_idx].alive:
            return seats[t_idx]
        for p in seats:
            if p.alive:
                return p
        return None

    def _ally_at(self, t_idx: int) -> Optional[Player]:
        """The ally an ALLY-only index names, counting teammates from 0."""
        allies = self._allies_in_obs_order()
        if t_idx < len(allies) and allies[t_idx].alive:
            return allies[t_idx]
        for a in allies:
            if a.alive:
                return a
        return None

    def _alive_enemy_indices(self) -> List[int]:
        """Target slots that currently point at a living enemy."""
        return [i for i, e in enumerate(self.engine.enemies[:MAX_ENEMIES])
                if e.alive]

    def _enemy_at(self, t_idx: int) -> Optional[Enemy]:
        """The enemy an action's target index names, with a fallback."""
        enemies = self.engine.enemies
        if t_idx < len(enemies) and enemies[t_idx].alive:
            return enemies[t_idx]
        for e in enemies[:MAX_ENEMIES]:
            if e.alive:
                return e
        return None

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
            engine.end_player_turn()
            if not engine.is_over:
                engine.run_enemy_turn()
            if not engine.is_over:
                engine.start_player_turn()
                self.active_player_idx = 0

    def _observe(self) -> np.ndarray:
        """Fixed layout: MAX_PLAYERS player triples, then MAX_ENEMIES enemy triples, always in that order..."""
        engine = self.engine
        buf = self._obs
        buf.fill(0.0)

        i = OBS_OFFSETS["players"][0]
        for p in self._obs_player_order()[:MAX_PLAYERS]:
            buf[i] = p.hp / max(1, p.max_hp)
            buf[i + 1] = p.block / 50.0
            buf[i + 2] = p.energy / max(1, p.max_energy)
            st = self._status_features(p)
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
            return buf.copy()

        base = OBS_OFFSETS["piles"][0]
        piles = (player.hand, player.draw_pile,
                 player.discard_pile, player.exhaust_pile)
        for p_idx, (pile, scale) in enumerate(zip(piles, (10.0, 30.0, 30.0, 30.0))):
            if not pile:
                continue
            i = base + p_idx * len(PILE_FEATURE_NAMES)
            buf[i] = len(pile) / scale
            for card in pile:
                t = card.card_type
                if t == CardType.ATTACK:
                    buf[i + 1] += 1.0
                elif t == CardType.SKILL:
                    buf[i + 2] += 1.0
                elif t == CardType.POWER:
                    buf[i + 3] += 1.0
                elif t == CardType.STATUS:
                    buf[i + 4] += 1.0
                else:
                    buf[i + 5] += 1.0
                buf[i + 6] += card.val("damage")
                buf[i + 7] += card.val("block")
            buf[i + 1:i + 6] /= scale
            buf[i + 6:i + 8] /= 100.0

        i = OBS_OFFSETS["hand"][0]
        playable = {id(c) for c in engine.playable_cards(player)}
        for card in player.hand[:MAX_HAND]:
            buf[i:i + HAND_FEATURES] = self._card_features(
                card, player, id(card) in playable)
            i += HAND_FEATURES

        lo, hi = OBS_OFFSETS["ally_summary"]
        buf[lo:hi] = party_summary(engine, self._obs_player_order(),
                                   MAX_PLAYERS - 1, MAX_HAND)
        return buf.copy()

    @staticmethod
    def _status_features(entity) -> List[float]:
        """One entity's status channels, in STATUS_CHANNEL_NAMES order."""
        st = entity.statuses
        if not st:
            return _NO_STATUSES
        g = st.get
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
        cost_f = 0.0 if cost == "X" else min(int(cost), 6) / 6.0
        t = card.card_type
        tm = card.target
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
            1.0 if tm == TargetMode.SINGLE_ENEMY else 0.0,
            1.0 if tm == TargetMode.ALL_ENEMIES else 0.0,
            1.0 if tm == TargetMode.SELF else 0.0,
            1.0 if tm == TargetMode.ALLY else 0.0,
            1.0 if tm == TargetMode.SELF_OR_ALLY else 0.0,
        ]

    def render(self) -> str:
        """Compact text board."""
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
        """Nothing to release -- no sockets, files or processes."""
        return None

    def hand_card_ids(self) -> np.ndarray:
        """Stable card id per hand slot, -1 for an empty slot."""
        ids = np.full(MAX_HAND, -1, dtype=np.int64)
        player = self._current_player()
        if player is None:
            return ids
        for i, card in enumerate(player.hand[:MAX_HAND]):
            ids[i] = card_id(card)
        return ids


try:
    import gymnasium as _gym
except ImportError:
    try:
        import gym as _gym
    except ImportError:
        _gym = None

_GymBase = _gym.Env if _gym is not None else object


class GymnasiumEnv(_GymBase):
    """Gymnasium-style 5-tuple view of CombatEnv."""

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

    def reset(self, seed=None, options=None):
        obs = self.env.reset(seed=seed)
        return obs, {"action_mask": self.env.legal_action_mask()}

    def step(self, action):
        obs, reward, done, info = self.env.step(int(action))
        truncated = bool(info.get("truncated", False))
        terminated = bool(done and not truncated)
        info = dict(info)
        info["action_mask"] = self.env.legal_action_mask()
        return obs, float(reward), terminated, truncated, info

    def render(self):
        return self.env.render()

    def close(self):
        return self.env.close()

    def action_masks(self):
        """Boolean mask, the name and dtype sb3-contrib expects."""
        return self.env.legal_action_mask().astype(bool)

    def __getattr__(self, name):
        return getattr(self.env, name)
