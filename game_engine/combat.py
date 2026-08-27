"""
CombatEngine: runs a full battle between 1-4 Players (coop, per confirmed
STS2 multiplayer supporting up to 4) and N Enemies.

This is the piece an RL wrapper (env.py) drives via discrete actions,
but it's also fully usable standalone for scripted/random playthroughs
(see demo.py).
"""

from typing import List, NamedTuple, Optional
from .entities import Player
from .enemies import Enemy, scale_enemy_for_players
from .cards import Card, CardType, TargetMode
from .statuses import StatusType


class _HandContext(NamedTuple):
    """The facts why_not_playable needs that describe the HAND AS A WHOLE
    rather than the card in front of it.

    Four of its rules ask a question about the whole hand, and each was
    re-answered per card. That made playable_cards O(hand^2): at a full hand
    of 10 it cost 300 element visits per call -- a membership scan, a
    play-cap scan and an Enthralled scan, each 10 long, once for every one
    of the 10 cards -- and env.py calls it twice per step. Answering them
    once per sweep makes it O(hand).

    This is a per-SWEEP SNAPSHOT, not a cache, and the distinction is the
    whole reason it is sound. playable_cards builds one, uses it across a
    single pass over a hand that cannot change mid-pass, and drops it;
    nothing survives the call. An earlier attempt to cache playable_cards
    ACROSS calls was dropped precisely because it had a window in which the
    hand could change underneath it (a test assigning `p.hand = [...]` was
    enough), and correctness depended on guessing the caller's pattern.
    Nothing here depends on any caller behaving a particular way.

    WHAT IS DELIBERATELY *NOT* IN HERE: a set of hand card ids, to answer
    "is this card in hand" in O(1). It was tried and measured slower at
    every hand size this game reaches. `card in player.hand` is a C-level
    scan of a list that is never longer than HAND_LIMIT (10), and building
    a Python set of 5 ids costs more than scanning 5 pointers. The win in
    this class came from the two rules that ALLOCATED a list per card, not
    from the membership test."""
    play_cap: Optional[int]           # lowest Sloth/Normality cap, or None
    first_enthralled: Optional[Card]  # the Enthralled that must be played first


class CombatEngine:
    def __init__(self, players: List[Player], enemies: List[Enemy], seed: Optional[int] = None,
                 act: str = "act1", scale_enemies: bool = True):
        """
        act: "act1" | "act2" | "act3" -- used for multiplayer enemy HP
             scaling (see enemies.PLAYER_COUNT_HP_SCALING). Defaults to
             act1 since this replica has no map/floor concept yet.
        scale_enemies: set False to spawn enemies at their raw base HP
             regardless of player count (useful for tests like the card
             pool smoke test, which wants a fixed punching bag).
        """
        assert 1 <= len(players) <= 4, "STS2 multiplayer supports 1 (solo) to 4 players"
        self.players = players
        self.enemies = enemies
        self.act = act   # kept so summon_enemy() can scale spawns the same way
        self.log: List[str] = []
        self.turn_number = 0
        self.seed = seed
        self._combat_over = False
        self._victory = False
        # Combat-wide (not per-turn) counter for cards like Midnight that
        # read "cards Exhausted this combat by ANYONE".
        self.total_exhausted_this_combat = 0
        # (damage, turns_remaining) bombs left behind by dead enemies with
        # Steam Eruption. Resolved at the end of a player turn.
        self.pending_eruptions: List = []
        # Installed by the driver to answer "choose a card" prompts; see
        # request_choice(). None means random, which is the old behaviour.
        self.choice_resolver = None

        for i, p in enumerate(self.players):
            p.start_combat(seed=(seed + i if seed is not None else None))
            p.engine = self   # lets Player.fire_hook() reach the engine
            self._apply_innate(p)
        for i, e in enumerate(self.enemies):
            if scale_enemies:
                scale_enemy_for_players(e, len(self.players), act)
            e.start_combat(seed=(seed + 100 + i if seed is not None else None))

    MAX_ENEMIES = 12

    def summon_enemy(self, new_enemies, summoner: Optional[Enemy] = None,
                      stunned: bool = False) -> List[Enemy]:
        """Bring one or more enemies into an ongoing fight.

        Everything a spawned enemy needs that the constructor normally does
        for the starting lineup happens here: multiplayer scaling, its own
        seeded rng, and joining `self.enemies` so targeting/AOE/victory
        checks see it.

        `stunned` gives the newcomer a do-nothing first turn, which is what
        the wiki describes for Phrog Parasite's Wrigglers and the Gremlin
        minions ("Spawned. Wakes up. Does nothing.").

        Capped at MAX_ENEMIES because two of the summoners are unbounded by
        their own text -- Two-Tailed Rat's "Call for Backup" summons another
        Two-Tailed Rat, which can itself Call for Backup. The real game
        presumably has a board limit; without one this is an infinite
        enemy-spawning loop, so the cap is a deliberate invention and is
        flagged as such in the README."""
        if isinstance(new_enemies, Enemy):
            new_enemies = [new_enemies]
        spawned = []
        for e in new_enemies:
            if len(self.enemies) >= self.MAX_ENEMIES:
                self.log.append(f"summon blocked: enemy cap ({self.MAX_ENEMIES}) reached")
                break
            scale_enemy_for_players(e, len(self.players), self.act)
            e.start_combat(seed=(self.seed + 500 + len(self.enemies)
                                  if self.seed is not None else None))
            if stunned:
                e.stunned_turns = 1
            if summoner is not None and e.leader is None:
                e.leader = summoner
            self.enemies.append(e)
            spawned.append(e)
            self.log.append(
                f"{summoner.name if summoner else 'The fight'} summons {e.name}")
        return spawned

    def handle_enemy_death(self, enemy: Enemy):
        """Fire an enemy's on_death effect, then clear out any minions whose
        leader just died. Called from _check_victory_defeat, which is the one
        place that already runs after every damage source."""
        if enemy.death_resolved:
            return
        enemy.death_resolved = True
        # Order matters: existing minions flee FIRST, then the death effect
        # summons. Doing it the other way round had the cleanup immediately
        # kill the reinforcements it had just spawned -- summon_enemy() marks
        # a spawn's leader as its summoner, so Gremlin Merc's two gremlins
        # were born already orphaned and were swept up by the same pass.
        for e in self.enemies:
            if e.alive and e.is_minion and e.leader is enemy:
                e.alive = False
                e.death_resolved = True
                self.log.append(f"{e.name} abandons the fight without its leader")
        # Steam Eruption: "when killed, deals X damage at the end of your
        # NEXT turn." A posthumous bomb rather than a self-destruct move.
        steam = enemy.get_status(StatusType.STEAM_ERUPTION)
        if steam > 0:
            self.pending_eruptions.append([steam, 1])
            self.log.append(f"{enemy.name} will erupt for {steam} at the end of your next turn")
        # Ravenous: "when an enemy dies, this creature immediately eats it,
        # becoming Stunned and gaining X Strength."
        for e in self.enemies:
            if not (e.alive and e is not enemy):
                continue
            rav = e.get_status(StatusType.RAVENOUS)
            if rav:
                e.add_status(StatusType.STRENGTH, rav)
                e.stunned_turns = max(e.stunned_turns, 1)
                self.log.append(f"{e.name} devours {enemy.name}: +{rav} Strength, stunned")
        if enemy.on_death is not None:
            enemy.on_death(self, enemy)

    @staticmethod
    def _apply_innate(player: Player):
        """Innate: "start each combat with this card in your Hand."

        Implemented by moving innate cards to the TOP of the draw pile
        rather than straight into the hand, which is what the real keyword
        does: they're drawn first as part of the opening hand, so having
        more innate cards than hand size still draws them all without
        handing out extra cards. `draw_pile.pop()` takes from the end, so
        "top" is the end of the list."""
        innate = [c for c in player.draw_pile if c.is_innate()]
        if not innate:
            return
        for c in innate:
            player.draw_pile.remove(c)
        player.draw_pile.extend(innate)

    # ---------- helpers used by card/enemy effects ----------
    def enemies_alive(self) -> List[Enemy]:
        return [e for e in self.enemies if e.alive]

    def players_alive(self) -> List[Player]:
        return [p for p in self.players if p.alive]

    def other_player(self, player: Player) -> Optional[Player]:
        """First other living player. Fine for 2-player coop; with 3-4
        players this is an arbitrary pick, not a real 'choose your ally'
        targeting system -- see other_players() and the note in
        /areas/sts2-combat-replica.md about wiring real ally-choice into
        env.py's action space."""
        for p in self.players:
            if p is not player and p.alive:
                return p
        return None

    def other_players(self, player: Player) -> List[Player]:
        """All other living players -- use this for anything that should
        genuinely consider every teammate in 3-4 player games."""
        return [p for p in self.players if p is not player and p.alive]

    def pick_enemy_attack_target(self) -> Player:
        """Very simple enemy targeting: random among living players."""
        alive = self.players_alive()
        if not alive:
            return self.players[0]
        picked = self.enemies[0].rng.choice(alive) if self.enemies else alive[0]
        # Intercept: "Redirect all incoming attacks that would be dealt to
        # another player this turn to you." Resolved at target-selection time
        # rather than on the damage itself, so the interceptor's own Block
        # and Thorns apply to the redirected hit -- which is the point of it.
        for p in alive:
            if p is not picked and picked in p.redirect_attacks_from:
                self.log.append(f"{p.name} intercepts the attack aimed at {picked.name}")
                return p
        return picked

    def random_alive_enemy(self, rng_owner: Player) -> Optional[Enemy]:
        """Random living enemy, for relics/cards that hit 'random' (e.g.
        Kusarigama, Parrying Shield). Uses the given player's own rng so
        results are reproducible under a combat seed."""
        alive = self.enemies_alive()
        if not alive:
            return None
        return rng_owner.rng.choice(alive)

    def draw_extra(self, player: Player, n: int):
        player.draw_cards(n, self.log)

    def has_enemy_category(self, category: str) -> bool:
        """Whether this fight contains an enemy of the given category
        ("elite"/"boss"). Checks ALL enemies, not just living ones, so a
        relic asking "is this a boss fight?" still gets the right answer
        after the boss has died."""
        return any(e.category == category for e in self.enemies)

    # ---------- turn structure ----------
    def start_player_turn(self):
        self.turn_number += 1
        # Gang Up reads "for each time ANOTHER player has attacked the enemy
        # this turn", so each enemy remembers who hit it, cleared here.
        for e in self.enemies:
            e.attacked_by_this_turn = []
            e.knockdown = None            # Knockdown lasts "this turn" only
        self.log.append(f"--- Turn {self.turn_number}: Player phase ---")
        for p in self.players:
            if p.alive:
                p.start_turn(self.log)
                p.acted_this_turn = False
                if p.pending_relic_block:
                    gained = p.gain_block(p.pending_relic_block, from_card=False)
                    self.log.append(f"{p.name} gains {gained} block (relic, promised last turn)")
                    p.pending_relic_block = 0
                if p.pending_relic_draw:
                    self.draw_extra(p, p.pending_relic_draw)
                    self.log.append(f"{p.name} draws {p.pending_relic_draw} additional cards (relic, promised last turn)")
                    p.pending_relic_draw = 0
                if p.pending_relic_energy:
                    p.energy += p.pending_relic_energy
                    self.log.append(f"{p.name} gains {p.pending_relic_energy} energy (relic, promised last turn)")
                    p.pending_relic_energy = 0
                # Relic "start of turn" effects fire here, AFTER this turn's
                # own block/hand/energy reset, not from __init__ -- see
                # relics.py's module docstring for why the ordering matters
                # (start_turn() would otherwise wipe Block/hand relics grant).
                # Fires EVERY turn, not just turn 1 -- each relic's own
                # callback checks turn_number for "start of combat"/"start
                # of your 2nd/3rd turn"/"every N turns" semantics.
                for relic in p.relics:
                    if relic.on_turn_start:
                        relic.on_turn_start(self, p, self.turn_number)
                # Same idea as relics' on_turn_start, but as a fireable event
                # so cards (Demon Form, Crimson Mantle, Pyre -- "at the
                # start of your turn, X") can register for it too via
                # register_hook, instead of needing their own bespoke
                # iteration mechanism like relics have.
                p.fire_hook("turn_start", turn_number=self.turn_number)
                self._tick_sandpit(p)

    def _tick_sandpit(self, player: Player):
        """Sandpit (The Insatiable): "In X turns, you will be eaten and die."
        A hard countdown on the player rather than damage -- it ticks at the
        start of each of their turns and kills at 0. The Frantic Escape
        status cards the boss shuffles in are the way back out: each play
        pushes the counter up.

        Driven here rather than through the generic status decay so the two
        can't both tick it; SANDPIT is marked PERMANENT for that reason."""
        stacks = player.get_status(StatusType.SANDPIT)
        if stacks <= 0:
            return
        player.add_status(StatusType.SANDPIT, -1)
        remaining = player.get_status(StatusType.SANDPIT)
        if remaining <= 0:
            player.hp = 0
            player.alive = False
            self.log.append(f"{player.name} is swallowed by the sandpit and DIES")
        else:
            self.log.append(f"{player.name} sinks: {remaining} turn(s) before being eaten")

    def request_choice(self, player: Player, options, prompt: str = "",
                        kind: str = "card"):
        """The single funnel for every "choose a card" the rules describe.

        Thirteen cards say CHOOSE rather than RANDOM -- Armaments, Headbutt,
        Wish, Discovery, Dual Wield and friends -- and every one of them was
        resolving with `rng.choice` or "just take the first one", because
        this replica had no choice interface anywhere. Random is the WORST
        case for most of them: Wish and Seeker Strike are tutors, so their
        measured power was a floor rather than an estimate.

        Drivers install `engine.choice_resolver` to answer properly:
        play.py prompts the human, bench.py scores the options. The default
        stays random so nothing regresses when a driver installs nothing --
        which is deliberately still the case for env.py, whose action space
        cannot express a mid-effect decision (see its module docstring).

        `kind` tells a resolver what it is choosing about ("upgrade",
        "exhaust", "to_hand", ...) so a heuristic can score sensibly instead
        of applying one rule to every prompt."""
        options = list(options)
        if not options:
            return None
        if len(options) == 1:
            return options[0]
        if self.choice_resolver is None:
            return player.rng.choice(options)
        chosen = self.choice_resolver(self, player, options, prompt, kind)
        # Identity, not equality (Card sets eq=False). A resolver returning
        # something that was never on offer would let a driver smuggle in an
        # arbitrary card, so fall back rather than trust it.
        if any(chosen is o for o in options):
            return chosen
        self.log.append(f"choice resolver returned an option that was not offered ({prompt})")
        return options[0]

    def _hand_context(self, player: Player) -> _HandContext:
        """Answer the hand-wide half of why_not_playable's rules, in ONE
        pass over the hand. See _HandContext for why this exists.

        Both hand-wide rules are read off `c.name` in the same loop, and
        neither allocates. That is the actual saving: the old code built a
        fresh list for the play cap AND a fresh list for the Enthralled
        search, per card -- so a 5-card hand allocated 10 throwaway lists
        per sweep, and a 10-card hand allocated 20."""
        cap = None
        first_enthralled = None
        caps = self.PLAY_CAP_CARDS
        for c in player.hand:
            name = c.name
            limit = caps.get(name)
            if limit is not None and (cap is None or limit < cap):
                cap = limit
            if first_enthralled is None and name == "Enthralled":
                first_enthralled = c
        return _HandContext(play_cap=cap, first_enthralled=first_enthralled)

    def why_not_playable(self, player: Player, card: Card,
                          ctx: Optional[_HandContext] = None) -> Optional[str]:
        """THE single source of truth for "may this card be played from
        hand". Returns None if it may, else a short human-readable reason.

        `ctx` is an optional pre-computed _HandContext, passed by
        playable_cards so one sweep answers the hand-wide questions once
        instead of once per card. Omit it -- as play_card does for its
        single card -- and one is built on the spot. Every RULE still lives
        here and nowhere else; only the SCANNING is shared.

        Both play_card() (which enforces) and playable_cards() (which
        advertises) go through this. They used to carry separate copies of
        the rules, and the copies drifted: Ringing, Smoggy and Bound were
        only ever checked in play_card, so playable_cards advertised cards
        the engine would then refuse. env.py's action mask had a THIRD copy,
        which knew about none of them -- an RL agent picking a masked-legal
        action would have it silently rejected and burn the step. Anything
        added here is automatically known to all three.

        Deliberately NOT here: auto-plays (Stampede, Hellraiser, Havoc,
        Mayhem) bypass these rules, because Ringing and Smoggy read as
        restrictions on what the PLAYER chooses to do. auto_play_card has
        its own, much smaller, set of guards."""
        if self._combat_over:
            return "combat is over"
        if ctx is None:
            ctx = self._hand_context(player)
        if card not in player.hand:
            return f"{card.name} not in {player.name}'s hand"
        # Unplayable is a KEYWORD, not just a big number. Gating on cost
        # alone meant a player with 999 energy could cast Wound, since the
        # UNPLAYABLE sentinel is itself 999.
        if card.is_unplayable():
            return f"{card.name} is unplayable"
        # Ringing (Ceremonial Beast): "You can only play 1 card this turn."
        if player.get_status(StatusType.RINGING) > 0 and player.cards_played_this_turn >= 1:
            return f"{player.name} has Ringing and has already played a card this turn"
        # Smoggy (Living Fog): "You can only play 1 Skill per turn."
        if (card.card_type == CardType.SKILL
                and player.get_status(StatusType.SMOGGY) > 0
                and player.skills_played_this_turn >= 1):
            return f"{player.name} has Smoggy and has already played a Skill this turn"
        # Bound (Queen): only one Bound card may be played per turn, no
        # matter how many you are holding or how many extra plays you have.
        if card.bound and player.bound_played_this_turn >= 1:
            return f"{card.name} is Bound and one Bound card has already been played"
        # Sloth / Normality, read off the hand every sweep so discarding the
        # card lifts the restriction immediately.
        cap = ctx.play_cap
        if cap is not None and player.cards_played_this_turn >= cap:
            return f"{player.name} cannot play more than {cap} cards this turn"
        # Enthralled: "If this is in your Hand, it must be played before
        # other cards." Only the FIRST one held matters, which is what the
        # context records.
        if ctx.first_enthralled is not None and card is not ctx.first_enthralled:
            return f"{player.name} must play Enthralled first"
        if card.playable_if is not None and not card.playable_if(card, player):
            return f"{card.name}'s play condition is not met"
        # An ALLY-targeting card with nobody to target is a guaranteed
        # fizzle, and Demonic Shield's fizzle costs 1 HP first. play.py
        # already filters is_multiplayer cards out of solo reward pools, but
        # that is not the only way one reaches a solo hand: Jack of All
        # Trades and Discovery both pull a RANDOM card into hand, and the
        # Colorless pool they draw from is full of ally cards.
        # NOT hoisted into _HandContext: `and` short-circuits, so this only
        # runs for an ALLY-targeting card, which is rare. Precomputing it
        # per sweep made every sweep pay for a check almost no sweep needs.
        if card.target == TargetMode.ALLY and not self.other_players(player):
            return f"{card.name} needs an ally and there is none"
        # X-cost cards are legal at 0 energy -- they just do nothing. Kept
        # legal rather than masked out, because a mask should encode what is
        # ALLOWED; whether it is worth doing belongs to the policy (bench's
        # greedy_policy filters these itself).
        cost = card.current_cost(player)
        if cost != "X" and player.energy < cost:
            return f"{player.name} lacks energy for {card.name}"
        return None

    def play_card(self, player: Player, card: Card, target: Optional[Enemy] = None,
                   ally_target: Optional[Player] = None) -> bool:
        """Returns True if the card was successfully played."""
        reason = self.why_not_playable(player, card)
        if reason is not None:
            # A combat that is already over is the one "refusal" that is
            # routine rather than a mistake, so it stays silent.
            if not self._combat_over:
                self.log.append(f"ILLEGAL: {reason}")
            return False

        card_cost = card.current_cost(player)
        is_x_cost = (card_cost == "X")
        actual_cost = player.energy if is_x_cost else card_cost

        resolved_target = None
        if card.target == TargetMode.SINGLE_ENEMY:
            if target is None or not target.alive:
                candidates = self.enemies_alive()
                if not candidates:
                    return False
                target = candidates[0]
            resolved_target = target
        elif card.target == TargetMode.ALLY:
            resolved_target = ally_target or self.other_player(player)
        elif card.target == TargetMode.ALL_ENEMIES:
            resolved_target = None  # effect loops enemies_alive() itself
        elif card.target in (TargetMode.SELF, TargetMode.SELF_OR_ALLY):
            resolved_target = ally_target if (card.target == TargetMode.SELF_OR_ALLY and ally_target) else player

        # Unrelenting's "the next Attack you play costs 0" is consumed here,
        # after the cost was computed from it but before the effect runs --
        # so Unrelenting itself can be the free Attack, and its own effect
        # then re-arms the flag for the following one.
        if card.card_type == CardType.ATTACK and player.next_attack_free:
            player.next_attack_free = False

        player.energy -= actual_cost
        player.hand.remove(card)
        cost_label = f"X={actual_cost}" if is_x_cost else str(actual_cost)
        self.log.append(f"{player.name} plays {card.name} (cost {cost_label})")
        player.cards_played_this_turn += 1
        if card.bound:
            player.bound_played_this_turn += 1
        # Tender: "Whenever you play a card, lose X Strength and X Dexterity
        # this turn." Applied per play, so a big turn compounds the penalty.
        tender = player.get_status(StatusType.TENDER)
        if tender:
            player.add_status(StatusType.STRENGTH_LOSS_THIS_TURN, tender)
            player.add_status(StatusType.DEXTERITY_LOSS_THIS_TURN, tender)
        if card.card_type == CardType.SKILL:
            player.skills_played_this_turn += 1
        if card.card_type == CardType.ATTACK:
            # Counted AFTER the cost was charged, so Stomp never discounts
            # itself, and BEFORE the effect, so Juggling's "third Attack you
            # play" sees the right number from inside attack_played.
            player.attacks_played_this_turn += 1

        effect_kwargs = {"x_amount": actual_cost} if is_x_cost else {}
        # Per-card damage relics (Strike Dummy, Miniature Cannon). Applied
        # for the whole card so multi-hit attacks get it on every hit, then
        # cleared -- deal_attack_damage adds it without consuming it.
        player.card_damage_bonus = self._card_damage_bonus(player, card)
        # Downgraded (Magi Knight): cards resolve as their un-upgraded
        # printing while it lives. Flipped for the duration of the effect
        # and restored after, so the card's real upgrade state is untouched.
        downgraded = player.get_status(StatusType.DOWNGRADED) > 0 and card.upgraded
        if downgraded:
            card.upgraded = False
        try:
            self.resolve_card_effect(player, card, resolved_target, **effect_kwargs)
        finally:
            if downgraded:
                card.upgraded = True
            player.card_damage_bonus = 0

        # Corruption: "Whenever you play a Skill, Exhaust it."
        forced_exhaust = player.exhaust_skills and card.card_type == CardType.SKILL
        if card.exhausts_now() or forced_exhaust:
            self.exhaust_card(player, card)
        elif self._goes_on_top_of_draw(player, card):
            player.draw_pile.append(card)
            self.log.append(f"{card.name} goes on top of {player.name}'s draw pile")
        else:
            player.discard_pile.append(card)

        self._check_victory_defeat()
        return True

    # Status/Curse cards that cap how many cards may be played while held.
    # Sloth is "each turn" and Normality "this turn"; with no deck editing
    # in scope the two behave identically here, since both last exactly as
    # long as the card stays in hand.
    PLAY_CAP_CARDS = {"Sloth": 3, "Normality": 3}

    def play_cap(self, player: Player):
        """Lowest play cap imposed by anything in hand, or None.

        The rule itself lives in _hand_context, which works it out in the
        same single pass as the other hand-wide facts -- keeping a second
        implementation here purely so this could be read standalone is
        exactly the kind of duplicate that drifts. This stays as the named
        way to ask the question."""
        return self._hand_context(player).play_cap

    def _goes_on_top_of_draw(self, player: Player, card: Card) -> bool:
        """Rebound ("put the NEXT card you play this turn on top of your Draw
        Pile") and Nostalgia ("the FIRST Attack or Skill you play each turn
        is placed on top of your Draw Pile"). Both replace the normal
        discard, so they are resolved at the one disposal site in play_card.

        Rebound is checked first and consumes its charge even when Nostalgia
        would also have fired, so the two can't both claim the same card and
        double-file it."""
        # Rebound arms "the NEXT card you play this turn". It must not fire
        # on Rebound itself: play_card runs this at Rebound's own disposal
        # step, immediately after its effect set the flag.
        armed_by = player.rebound_next_card
        if armed_by is not None and armed_by is not card:
            player.rebound_next_card = None
            return True
        if (player.nostalgia and not player.nostalgia_done_this_turn
                and card.card_type in (CardType.ATTACK, CardType.SKILL)):
            player.nostalgia_done_this_turn = True
            return True
        return False

    def resolve_card_effect(self, player: Player, card: Card,
                             target: Optional[Enemy] = None, **effect_kwargs):
        """Run a card's effect and fire every 'a card was played' event it
        should trigger -- with NO cost/hand/discard bookkeeping.

        play_card() calls this once it has paid the cost and removed the
        card from hand. Cards that play OTHER cards (Havoc, Cascade) call
        it directly: they previously invoked `played.effect(...)` raw,
        which silently skipped card_played/attack_played/skill_played/
        power_played and the enemy_died broadcast -- so a card played by
        Havoc didn't trigger Rage, Juggernaut, or any relic keyed on card
        plays, while the identical card played by hand did. Sharing one
        code path is what keeps those two from drifting apart again."""
        enemies_before = {id(e) for e in self.enemies if e.alive}
        for e in self.enemies:
            e.hit_by_current_card = False

        card.effect(self, player, target, card, **effect_kwargs)
        self._resolve_skittish()
        player.acted_this_turn = True
        # Counted here rather than in play_card so Gold Axe ("damage equal to
        # the number of cards played this combat") also counts cards played
        # FOR you by Havoc, Cascade, Mayhem and Stampede -- they all funnel
        # through this one method.
        player.cards_played_this_combat += 1
        player.fire_hook("card_played", card=card)
        if card.card_type == CardType.ATTACK:
            player.fire_hook("attack_played", card=card)
        elif card.card_type == CardType.SKILL:
            player.fire_hook("skill_played", card=card)
        elif card.card_type == CardType.POWER:
            player.fire_hook("power_played", card=card)

        newly_dead = [e for e in self.enemies if not e.alive and id(e) in enemies_before]
        if newly_dead:
            for p in self.players:
                if p.alive:
                    for _ in newly_dead:
                        p.fire_hook("enemy_died")

        # One-Two Punch: "your next Attack is played an extra time". Handled
        # here rather than in play_card so it covers every route a card can
        # be played (hand, Havoc, Cascade, Stampede), the same reason those
        # were unified in the first place. The guard stops the extra play
        # from consuming another charge and recursing.
        # Three routes to "played an extra time", all sharing one guard so
        # they can't chain into each other or recurse: One-Two Punch
        # (Attacks only), Duplicator (any card), and the Replay keyword
        # (Soldier's Stew, granted per-card).
        replays = 0
        if not player._replaying_attack and not self._combat_over:
            if card.card_type == CardType.ATTACK and player.extra_attack_plays > 0:
                player.extra_attack_plays -= 1
                replays += 1
            if player.extra_card_plays > 0:
                player.extra_card_plays -= 1
                replays += 1
            replays += card.replay
        if replays:
            player._replaying_attack = True
            try:
                for _ in range(replays):
                    if self._combat_over:
                        break
                    self.log.append(f"{card.name} is played an extra time")
                    self.resolve_card_effect(player, card, target, **effect_kwargs)
            finally:
                player._replaying_attack = False

    AUTO_PLAY_MAX_DEPTH = 5

    def auto_play_card(self, player: Player, card: Card, target: Optional[Enemy] = None,
                        source: str = "", from_exhaust: bool = False) -> bool:
        """Play a card outside the normal pay-cost-from-hand flow.

        Used by every "this card is played for you" effect: Hellraiser
        (on draw), Stampede (at end of turn), Howl from Beyond (from the
        exhaust pile). No energy is paid and no targeting menu is consulted.

        Depth-capped because these can chain: Hellraiser plays a drawn
        Pommel Strike, which draws more cards, which may be more Strikes.
        The chain does terminate on its own once the deck runs dry, but a
        cap turns a pathological deck into a bounded no-op instead of a
        stack overflow -- the same bounded-loop discipline the benchmark
        harnesses use."""
        if self._combat_over or not player.alive:
            return False
        if player._auto_play_depth >= self.AUTO_PLAY_MAX_DEPTH:
            self.log.append(f"{card.name} not auto-played ({source}): chain depth cap reached")
            return False
        if card.card_type == CardType.STATUS:
            return False

        resolved = target
        if card.target == TargetMode.SINGLE_ENEMY and (resolved is None or not resolved.alive):
            alive = self.enemies_alive()
            if not alive:
                return False
            resolved = alive[0]
        elif card.target in (TargetMode.SELF, TargetMode.SELF_OR_ALLY):
            resolved = player
        elif card.target == TargetMode.ALLY:
            resolved = self.other_player(player)

        if card in player.hand:
            player.hand.remove(card)
        self.log.append(f"{player.name} plays {card.name} automatically ({source})")

        player._auto_play_depth += 1
        try:
            self.resolve_card_effect(player, card, resolved)
        finally:
            player._auto_play_depth -= 1

        # Howl from Beyond is played FROM the exhaust pile and stays there,
        # which is what makes it a recurring effect; everything else follows
        # the normal post-play routing.
        if not from_exhaust:
            if card.exhausts_now() or (player.exhaust_skills and card.card_type == CardType.SKILL):
                self.exhaust_card(player, card)
            else:
                player.discard_pile.append(card)
        self._check_victory_defeat()
        return True

    def use_potion(self, player: Player, potion, target: Optional[Enemy] = None) -> bool:
        """Potions aren't Cards -- no cost, no hand/discard/exhaust pile,
        no card_type -- so this is a separate, parallel method to
        play_card() rather than shoehorning potions through it. Removes
        the potion from inventory, runs its effect, and fires 'use_potion'
        for relics like Reptile Trinket ('whenever you use a Potion...')."""
        if self._combat_over:
            return False
        if potion not in player.potions:
            self.log.append(f"ILLEGAL: {potion.name} not in {player.name}'s inventory")
            return False
        if potion.target == "enemy" and (target is None or not target.alive):
            return False

        player.potions.remove(potion)
        self.log.append(f"{player.name} uses {potion.name}")
        potion.effect(self, player, target=target)
        player.fire_hook("use_potion", potion=potion)

        self._check_victory_defeat()
        return True

    def exhaust_card(self, player: Player, card: Card):
        """Move a card into player's exhaust pile and update every counter
        real cards read off of it (Dark Embrace/Feel No Pain-style 'whenever
        a card is exhausted' powers aren't implemented as hooks yet, but the
        counters they'd need -- exhausted_this_turn, total_exhausted_this_combat
        -- are tracked here so those powers are a small follow-up, not a
        re-plumb). Safe to call whether the card is currently in hand,
        discard, or already removed from both (e.g. the card being played)."""
        if card in player.hand:
            player.hand.remove(card)
        elif card in player.discard_pile:
            player.discard_pile.remove(card)
        player.exhaust_pile.append(card)
        player.exhausted_this_turn.append(card)
        self.total_exhausted_this_combat += 1
        self.log.append(f"{player.name} exhausts {card.name}")
        player.fire_hook("card_exhausted", card=card)

    def end_player_turn(self):
        # Same guard play_card/use_potion/run_enemy_turn already have.
        # Without it, calling this after a win re-ran _check_victory_defeat(),
        # which re-fired every on_combat_end relic (Burning Blood healing
        # twice, "VICTORY" logged twice). play.py's loop happens to break
        # before reaching here, but env.py's _advance_sub_turn() calls it
        # unconditionally, so the RL path hit it.
        if self._combat_over:
            return
        for p in self.players:
            if p.alive:
                # Fired BEFORE end_turn(), which wipes turn-scoped statuses
                # and hooks -- Stampede and Howl from Beyond both need the
                # hand and this turn's state to still exist.
                p.fire_hook("turn_end")
        if self._combat_over:
            return
        for p in self.players:
            if p.alive:
                # These read "if this is in your Hand at end of turn", so
                # they must run BEFORE end_turn() discards the hand.
                self._resolve_constrict(p)
                self._resolve_infection(p)
                for c in p.hand + p.draw_pile + p.discard_pile:
                    c.bound = False   # "cards are un-Bound at end of turn"
                self._resolve_eruptions(p)
                p.end_turn(self.log)
                for relic in p.relics:
                    if relic.on_turn_end:
                        relic.on_turn_end(self, p)
        self._check_victory_defeat()

    @staticmethod
    def _card_damage_bonus(player: Player, card: Card) -> int:
        """Flat per-card damage from relics that key off the card itself.
        Kept in one place so the two relics that do this can't drift."""
        if card.card_type != CardType.ATTACK:
            return 0
        bonus = 0
        for relic in player.relics:
            if relic.name == "Strike Dummy" and "Strike" in card.name:
                bonus += 3
            elif relic.name == "Miniature Cannon" and card.upgraded:
                bonus += 3
        return bonus

    def _resolve_eruptions(self, player: Player):
        """Steam Eruption's posthumous damage, ticking down at the end of
        each player turn."""
        still = []
        for bomb in self.pending_eruptions:
            bomb[1] -= 1
            if bomb[1] <= 0:
                player.take_damage(bomb[0], source_is_attack=False,
                                    log=self.log, label="Steam Eruption")
            else:
                still.append(bomb)
        self.pending_eruptions = still

    def _resolve_skittish(self):
        """Skittish: "The first time this creature is hit each turn, it gains
        X Block." Fires once per CARD, not per hit -- the wiki is explicit
        that a multi-hit card like Twin Strike lands both hits before the
        Block appears, so this runs after the whole card resolves rather than
        inside take_damage()."""
        for e in self.enemies:
            if not (e.alive and e.hit_by_current_card):
                continue
            e.hit_by_current_card = False
            amount = e.get_status(StatusType.SKITTISH)
            if amount > 0 and not e.skittish_used_this_turn:
                e.skittish_used_this_turn = True
                gained = e.gain_block(amount)
                self.log.append(f"{e.name} gains {gained} block (Skittish)")

    def _resolve_constrict(self, player: Player):
        """Slithering Strangler's Constrict: 'while the Slithering
        Strangler is alive, at the end of your turn, take N damage'
        (N = stack count). Fixed engine rule, not a registered hook,
        matching how Poison/Regen are direct logic rather than opt-in
        Powers. Approximation: checks for ANY living enemy named
        'Slithering Strangler' rather than tracking which specific
        instance applied the stacks, since a fight realistically has at
        most one."""
        stacks = player.get_status(StatusType.CONSTRICT)
        if stacks <= 0:
            return
        if any(e.alive and e.name == "Slithering Strangler" for e in self.enemies):
            player.take_damage(stacks, source_is_attack=False, log=self.log, label="Constrict")

    # name -> (amount, is_hp_loss). Cards that punish you for still holding
    # them at end of turn. Infection deals DAMAGE (Block absorbs it); Beckon
    # says "lose 6 HP", which ignores Block -- the distinction is the whole
    # reason this is a table of two fields rather than one number.
    # "At the end of your turn, if this is in your Hand, ..." -- every
    # Status and Curse of that shape. (kind, amount, exhausts) where kind is
    # "damage" (Block stops it), "hp_loss" (Block does not), "hp_per_card"
    # (Regret), or a StatusType to apply to the holder.
    #
    # This started as an Infection-only branch, became a 3-field tuple table
    # for Beckon and Toxic, and grew a `kind` field once the curses arrived,
    # because Doubt and Shame apply a debuff rather than dealing damage.
    END_OF_TURN_HAND_PENALTIES = {
        "Infection":      ("damage", 3, False),
        "Beckon":         ("hp_loss", 6, False),
        "Toxic":          ("damage", 5, True),   # exhausts itself after biting
        "Burn":           ("damage", 2, False),
        "Disintegration": ("damage", 6, False),
        # Curses
        "Bad Luck":       ("hp_loss", 13, False),
        "Decay":          ("damage", 2, False),
        "Regret":         ("hp_per_card", 1, False),
        "Doubt":          (StatusType.WEAK, 1, False),
        "Shame":          (StatusType.FRAIL, 1, False),
    }

    def _resolve_infection(self, player: Player):
        """Resolve every "if this is in your Hand at end of turn" status
        card. Started as an Infection-only rule; Soul Fysh's Beckon made it
        the second, so it is now a small table rather than a third copy of
        the same scan."""
        # Wither is handled separately: Aeonglass escalates its damage, so
        # the number lives on the card instead of in the table above.
        for card in [c for c in player.hand if c.name.startswith("Wither")]:
            player.take_damage(card.val("damage", 3), source_is_attack=False,
                                log=self.log, label=card.name)
        for name, (kind, amount, exhausts) in self.END_OF_TURN_HAND_PENALTIES.items():
            held = [c for c in player.hand if c.name == name]
            for card in held:
                if kind == "hp_loss":
                    player.lose_hp(amount, log=self.log, label=name)
                elif kind == "damage":
                    player.take_damage(amount, source_is_attack=False,
                                        log=self.log, label=name)
                elif kind == "hp_per_card":
                    # Regret: "lose 1 HP for each card in your Hand" --
                    # counting itself, which is why holding it alone still
                    # costs 1.
                    player.lose_hp(amount * len(player.hand), log=self.log, label=name)
                else:
                    # Deferred: Player.end_turn applies these AFTER
                    # decay_statuses_end_of_turn. Applying here would give 1
                    # Weak and then immediately decrement it to 0, so Doubt
                    # and Shame did nothing at all.
                    player.pending_end_of_turn_statuses.append((kind, amount, name))
                if exhausts:
                    self.exhaust_card(player, card)

    def run_enemy_turn(self):
        if self._combat_over:
            return
        # Ambergris: "take an extra turn". Implemented by skipping the enemy
        # phase entirely -- every driver (play.py, env.py, bench.py) already
        # loops start_player_turn -> end_player_turn -> run_enemy_turn, so
        # consuming the charge here gives a genuine extra turn without any
        # of them needing to know about it.
        extra = [p for p in self.players_alive() if p.extra_turns > 0]
        if extra:
            for p in extra:
                p.extra_turns -= 1
            self.log.append("The enemies lose their turn (extra turn taken)")
            return
        self.log.append(f"--- Turn {self.turn_number}: Enemy phase ---")
        # Snapshot: an enemy summoned mid-phase must NOT also act this turn.
        # Iterating self.enemies directly would include anything appended by
        # a summon that just resolved.
        # Reattach: "if other segments are still alive, revives in 2 turns."
        for e in list(self.enemies):
            if e.revive_in > 0:
                e.revive_in -= 1
                if e.revive_in <= 0 and e.on_revive is not None:
                    e.on_revive(self, e)
        for e in list(self.enemies):
            if e.alive and self.players_alive():
                if e.stunned_turns > 0:
                    e.stunned_turns -= 1
                    self.log.append(f"{e.name} is stunned and does nothing")
                    continue
                e.take_turn(self)
                for p in self.players:
                    if p.alive:
                        p.fire_hook("enemy_turn_end", enemy=e)
                self._check_victory_defeat()
                if self._combat_over:
                    break

    def _check_victory_defeat(self):
        # Resolve deaths BEFORE deciding the fight is over: an enemy whose
        # death summons reinforcements (Gremlin Merc, Phrog Parasite) must
        # get to spawn them, or killing the last enemy on the field would
        # end the combat and skip the second half of the encounter.
        for e in list(self.enemies):
            if not e.alive and not e.death_resolved:
                self.handle_enemy_death(e)
        if not self.players_alive():
            self._combat_over = True
            self._victory = False
            self.log.append("=== DEFEAT: all players down ===")
        elif not self.enemies_alive():
            self._combat_over = True
            self._victory = True
            self.log.append("=== VICTORY: all enemies defeated ===")
            for p in self.players:
                if p.alive:
                    for relic in p.relics:
                        if relic.on_combat_end:
                            relic.on_combat_end(self, p)
            # Combat-scoped card mutations all end here.
            for p in self.players:
                p.revert_combat_upgrades()
                p.clear_temp_costs("combat")
                p.clear_temp_replays()

    @property
    def is_over(self) -> bool:
        return self._combat_over

    @property
    def victory(self) -> bool:
        return self._victory

    def playable_cards(self, player: Player) -> List[Card]:
        """Every card in hand that play_card would actually accept right
        now. Shares why_not_playable with play_card, so the advertised list
        and the enforced rules cannot drift apart.

        One _HandContext is built for the whole sweep -- see _HandContext for
        why that is a snapshot rather than a cache."""
        ctx = self._hand_context(player)
        return [c for c in player.hand
                if self.why_not_playable(player, c, ctx) is None]
