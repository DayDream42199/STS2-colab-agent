import random
from enum import Enum

from ..Context.context import Context, PendingChoice
from ..Context.rng_streams import RngStreams
from ..Events.game_event import GameEvent
from ..Resolution.resolver import Resolver
from ..Registry.card_registry import create_card
from ..Registry.unit_registry import create_enemy
from ..Cards._card import Card
from ..Cards._card_enums import CardType, TargetType
from ..Cards._card_ref import is_upgraded, new_ref, take
from ..Cards._text import card_text
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_move_card import InstantMoveCard
from ..Effects.InstantEffects.instant_summon import InstantSummon
from ..Effects.StatusEffects.minion import Minion
from ..Effects.StatusEffects.stun import Stun
from ..Units.Enemies._scripted import hp_scale, block_scale
from ..Effects.InstantEffects.instant_play_card import InstantPlayCard


class CombatPhase(Enum):
    NOT_STARTED = "NOT_STARTED"
    PLAYER_TURN = "PLAYER_TURN"
    ENEMY_TURN = "ENEMY_TURN"
    OVER = "OVER"


class _Hits:
    """Which damage in one list of effects is one hit, so the dealer is
    looked at once per hit, as the game's AttackCommand does: a hit lands on
    all its targets, then the attack stops if the attacker has died (Thorns,
    Flame Barrier). A hit is one `hit` number (enemy attacks and the cards
    that roll a target per hit number theirs), or else a run of damage from
    one source until a target comes round again: Whirlwind's e1 e2 | e1 e2,
    Twin Strike's e1 | e1."""

    def __init__(self):
        self.source = self.number = None
        self.targets = set()
        self.dealer_alive = True

    def mark(self, effect):
        if not isinstance(effect, InstantDamage):
            return
        number = getattr(effect, "hit", None)
        if (effect.source is not self.source
                or (number is not None and number != self.number)
                or (number is None and effect.target in self.targets)):
            self.source, self.number, self.targets = effect.source, number, set()
            self.dealer_alive = effect.source.is_alive()
        self.targets.add(effect.target)
        effect.dealer_alive = self.dealer_alive


class CombatResult(Enum):
    VICTORY = "VICTORY"
    DEFEAT = "DEFEAT"


class Combat:
    HAND_SIZE = 5
    # Co-op is one to four players. Refused at construction rather than
    # scaled into nonsense: hp_scale and block_scale keep multiplying past it.
    MAX_ALLIES = 4
    # A reaction may cause a reaction; bounded so two powers cannot ping-pong.
    MAX_EVENT_DEPTH = 3
    # Havoc turning up Havoc is legal, and has to terminate.
    MAX_PLAY_DEPTH = 3
    # Cards in hand react only to these. CARD_DRAWN is not here: it goes to
    # the cards that were drawn, not to the whole hand.
    HAND_EVENTS = (GameEvent.TURN_END,)

    # Per turn, stepped by the event's `amount`: hp_lost is HP, not hits.
    COUNTED_EVENTS = {
        GameEvent.HP_LOST: "hp_lost",
        GameEvent.BLOCK_GAINED: "block_gained",
        GameEvent.CARD_PLAYED: "cards_played",
        GameEvent.CARD_DRAWN: "cards_drawn",
        GameEvent.CARD_EXHAUSTED: "cards_exhausted",
    }

    # Per combat, stepped by 1: Tear Asunder counts times, not amounts.
    COMBAT_COUNTED_EVENTS = {
        GameEvent.CARD_PLAYED: "cards_played",
        GameEvent.HP_LOST: "hp_lost_events",
    }

    def __init__(self, allies, enemies, rng=None, act="act1", scale_enemies=True):
        self.allies = list(allies)
        self.enemies = list(enemies)
        if not 1 <= len(self.allies) <= self.MAX_ALLIES:
            raise ValueError(
                f"A combat takes 1 to {self.MAX_ALLIES} players, not {len(self.allies)}.")
        # One random stream per purpose (rng_streams.py). Given streams are
        # used as they are; a single random.Random seeds a set; none draws a
        # seed and keeps it, so even this fight can be played again.
        if isinstance(rng, RngStreams):
            self.rngs = rng
        elif rng is not None:
            self.rngs = RngStreams.from_rng(rng)
        else:
            self.rngs = RngStreams(random.SystemRandom().randrange(2 ** 32))
        self.seed = self.rngs.seed
        # For callers that want "a seeded rng" and no stream in particular.
        self.rng = self.rngs.niche
        # Co-op scaling: enemy HP is multiplied by player count and an act
        # factor, as in STS2. Off for a test that wants the printed numbers.
        self.act = act
        self.scale_enemies = scale_enemies

        self.phase = CombatPhase.NOT_STARTED
        self.result = None
        self._event_depth = 0
        self._play_depth = 0
        # Numbers each card play (Context.play_id), the game's CardPlay.
        self._play_serial = 0
        # 1 on the first player turn. Mirrored into combat_counters["turn"] so
        # an enemy choosing its intent can read it (a Two-Tailed Rat group
        # calls for backup at most once a turn).
        self.turn_number = 0
        # Whole-fight tallies belonging to no unit: a card counting "by ANYONE".
        self.combat_counters = {}

        # Questions raised by the action being resolved, and the ones now
        # waiting on a player, by the unit id of whoever has to answer.
        self._asks = []
        self.pending_choices = {}
        # False means nobody is there to ask, so questions are answered at
        # random - what a headless or training run wants, and what the whole
        # game did before choices existed. Session sets it when a client joins.
        self.ask_players = False
        # Players who have left: their questions are answered at random too,
        # or a fight would wait forever on someone who is not coming back.
        self.unattended = set()
        # This player turn, by unit id: who has ended it (the game's "ready";
        # playing a card takes it back), and who chose to wait since anything
        # last changed. Whoever runs the players - the session - ends the
        # round once everyone still there has ended.
        self.ended_turn = set()
        self.waiting = set()

    # --- lifecycle -------------------------------------------------------

    def start(self):
        # One at a time, as the game's CombatRoom creates them: each rolls
        # against the ones before it, which already carry their scaling.
        for index, enemy in enumerate(self.enemies):
            self._roll_hp(enemy, self.enemies[:index])
            self._scale_enemy(enemy)
        for enemy in list(self.enemies):
            self._enemy_enters(enemy)

        for ally in self.allies:
            self._build_draw_pile(ally)
            self._emit(GameEvent.BEFORE_HAND_DRAW, ally)
            self._turn_draw(ally)

        self._new_turn()
        for enemy in self.enemies:
            enemy.choose_intent(self._context_for(enemy))

        self.phase = CombatPhase.PLAYER_TURN
        for unit in self.allies + self.enemies:
            unit.reset_turn_counters()
        for ally in self.allies:
            self._emit(GameEvent.TURN_START, ally)

    def _new_turn(self):
        self.turn_number += 1
        self.combat_counters["turn"] = self.turn_number

    def _roll_hp(self, enemy, others):
        """Roll an enemy's max HP as it enters the fight, if it was built
        without an rng (the session's and summons' are): from the Niche
        stream, among the values its range allows that no living enemy
        already here has - the game's SetUniqueMonsterHpValue, so two Nibbits
        alone are never the same - or from the whole range if all are taken.
        In co-op the others already carry their scaled HP, which seldom falls
        in the range, so there two can match; the game's code does the same."""
        if not getattr(enemy, "hp_unrolled", False):
            return
        low, high = enemy.hp_range
        taken = {other.max_hp for other in others if other.is_alive()}
        free = [hp for hp in range(low, high + 1) if hp not in taken]
        enemy.max_hp = enemy.current_hp = (self.rngs.niche.choice(free) if free
                                           else self.rngs.niche.randint(low, high))
        enemy.hp_unrolled = False

    def _scale_enemy(self, enemy):
        """Co-op scaling, once, for an enemy present at the start or summoned
        later. Bosses and slimes alike."""
        if not self.scale_enemies:
            return
        players = len(self.allies)
        mult = hp_scale(players, self.act)
        if mult != 1.0:
            enemy.max_hp = max(1, round(enemy.max_hp * mult))
            enemy.current_hp = enemy.max_hp
        enemy.block_scale = block_scale(players, self.act)

    # --- summoning ----------------------------------------------------------

    def summon(self, type_ids, summoner=None, stunned=False, minion=False):
        """Bring enemies into an ongoing fight. Returns them.

        Each arrives scaled for the party, with a unit id nobody holds, an
        intent already chosen on the players' turn (so the client sees it at
        once; on the enemies' turn it comes with everyone's), and `summoner`
        as its leader. It does not act in the enemy phase that summoned it -
        the phase walks a snapshot of the lineup - and `stunned` makes it sit
        out the next one as well, as the reference does for backup."""
        arrived = []
        for type_id in type_ids:
            # HP from Niche as it arrives, moves from MonsterAi, as the game
            # rolls them.
            enemy = create_enemy(type_id, self._free_enemy_id())
            enemy.rng = self.rngs.monster_ai
            self._roll_hp(enemy, self.enemies)
            self._scale_enemy(enemy)
            enemy.leader = summoner
            if minion:
                enemy.apply_status(Minion(source=summoner, target=enemy))
            if stunned:
                enemy.apply_status(Stun(source=summoner, target=enemy, amount=1))
            self.enemies.append(enemy)
            self._enemy_enters(enemy)
            if self.phase != CombatPhase.ENEMY_TURN:
                # On the enemies' turn it picks its move with everyone else
                # once that turn is over, as the game's AfterCreatureAdded
                # rolls only on the players' side - not twice.
                enemy.choose_intent(self._context_for(enemy))
            arrived.append(enemy)
        return arrived

    def _enemy_enters(self, enemy):
        """What an enemy does as it arrives - Cubex's Block and Artifact."""
        on_start = getattr(enemy, "on_combat_start", None)
        if on_start is None:
            return
        for effect in on_start(self._context_for(enemy)) or ():
            self._resolve(effect)

    def _free_enemy_id(self):
        n = len(self.enemies) + 1
        while self.find_unit(f"e{n}") is not None:
            n += 1
        return f"e{n}"

    def _resolve_summon(self, effect):
        arrived = self.summon(effect.type_ids, summoner=effect.source,
                              stunned=effect.stunned, minion=effect.minion)
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": effect.source.unit_id,
            "summoned": [e.unit_id for e in arrived],
            "amount": len(arrived),
        }

    def _resolve_deaths(self):
        """Run what a dead enemy does on dying, once, before the fight can end.

        Phrog Parasite's Wrigglers arrive here, so killing it as the last
        enemy does not win the fight. Then any Minion whose leader just died
        leaves, with no death of its own to resolve: it left, it was not
        killed. Loops because a death can cause another."""
        progress = True
        while progress:
            progress = False
            for enemy in list(self.enemies):
                if enemy.is_alive() or getattr(enemy, "death_resolved", False):
                    continue
                enemy.death_resolved = True
                progress = True
                for other in self.enemies:
                    if (other.is_alive() and getattr(other, "leader", None) is enemy
                            and other.get_status("minion") is not None):
                        other.current_hp = 0
                        other.death_resolved = True
                on_death = getattr(enemy, "on_death", None)
                if on_death is not None:
                    for effect in on_death(self._context_for(enemy)) or ():
                        self._resolve(effect)
                if enemy.is_alive():
                    # It did not die after all (Waterfall Giant's Steam
                    # Eruption): its real death is still to come.
                    enemy.death_resolved = False
                elif getattr(enemy, "revive_in", 0) <= 0:
                    # Gone for good (an Illusion coming back is not): the other
                    # enemies may react - Corpse Slug's Ravenous.
                    self._emit(GameEvent.ENEMY_DIED, enemy)
        # And as the game's CreatureCmd.Kill: once only Minions are left
        # standing - no enemy of its own right, alive or about to revive - they
        # go too (The Kin's followers when the Priest falls).
        living = [e for e in self.enemies if e.is_alive()]
        primary_left = any(e.get_status("minion") is None and (e.is_alive() or getattr(e, "revive_in", 0) > 0)
                           for e in self.enemies)
        if living and not primary_left:
            for enemy in living:
                enemy.current_hp = 0
                enemy.death_resolved = True

    def _revive_due(self):
        """After an enemy phase: an enemy scheduled to come back (Illusion)
        counts down, and returns with a fresh intent when it reaches zero."""
        for enemy in self.enemies:
            due = getattr(enemy, "revive_in", 0)
            if enemy.is_alive() or due <= 0:
                continue
            enemy.revive_in = due - 1
            if enemy.revive_in <= 0:
                enemy.revive()          # the intent loop that follows gives it a move

    def is_over(self):
        return self.result is not None

    def find_unit(self, unit_id):
        for unit in self.allies + self.enemies:
            if unit.unit_id == unit_id:
                return unit
        return None

    # --- player actions ----------------------------------------------------

    def play_card(self, ally, hand_index, target=None):
        if self.phase != CombatPhase.PLAYER_TURN:
            raise RuntimeError("It is not the player turn.")
        if not ally.is_alive():
            raise ValueError(f"{ally.unit_id} has been defeated and cannot act.")
        if ally.unit_id in self.pending_choices:
            raise ValueError(f"{ally.unit_id} has a choice to answer first.")
        if not (0 <= hand_index < len(ally.hand)):
            raise IndexError(f"hand_index {hand_index} out of range.")

        card_id = ally.hand[hand_index]
        card = create_card(card_id)

        if not card.properties.playable:
            raise ValueError(f"{card.name} cannot be played.")

        # These all read the whole hand, and all come before the cost: a play
        # the hand forbids must not spend energy.
        cap = self._play_cap(ally)
        if self._capped(ally):
            raise ValueError(
                f"{ally.unit_id} cannot play more than {cap} cards this turn.")
        locked = self._must_play_first(ally)
        if locked is not None and locked is not card_id:
            raise ValueError(f"{create_card(locked).name} must be played first.")
        if not card.playable_now(ally):
            raise ValueError(f"{card.name} cannot be played out of this hand.")
        if self._forbidden(ally, card):
            raise ValueError(f"{card.name} cannot be played this turn.")

        cost = self.card_cost(ally, card)
        if ally.energy < cost:
            raise ValueError(f"Not enough energy to play {card.name}.")

        resolved_target = self._resolve_target(card, ally, target)

        # Playing after ending takes the end back; whoever waited looks again.
        self.ended_turn.discard(ally.unit_id)
        self.waiting.clear()
        ally.spend_energy(cost)
        ally.hand.pop(hand_index)

        # An X-cost card spends everything, and needs to be told how much.
        x_amount = cost if card.cost == Card.X_COST else 0
        results = self._play(ally, card_id, card, resolved_target,
                             x_amount=x_amount)
        results.extend(self._drain_asks())
        return results

    def end_turn(self, ally):
        """`ally` is done for this turn. They may still play, which takes it
        back; the round ends once everyone still there has ended
        (end_player_turn, called by whoever runs the players)."""
        self._check_may_act(ally)
        self.ended_turn.add(ally.unit_id)
        self.waiting.clear()

    def wait(self, ally):
        """`ally` lets the others move first. Nothing in the fight changes;
        the next play, answer or end turn, by anyone, clears it and they
        decide again. Allowed only while may_wait says so."""
        self._check_may_act(ally)
        if not self.may_wait(ally):
            raise ValueError("Nobody else is still to act: play a card or end your turn.")
        self.waiting.add(ally.unit_id)

    def may_wait(self, ally):
        """Whether `ally` may wait: not ended, not already waiting, and
        someone else can still move the turn on. So waiting can never stall a
        round - of the players who have not ended, one has always not waited."""
        if ally.unit_id in self.ended_turn or ally.unit_id in self.waiting:
            return False
        return any(self._still_to_act(other) for other in self.allies if other is not ally)

    def _still_to_act(self, ally):
        """A question to answer, or not yet ended or waiting. Never a player
        who left: nobody is there to act for them."""
        if not ally.is_alive() or ally.unit_id in self.unattended:
            return False
        if ally.unit_id in self.pending_choices:
            return True
        return ally.unit_id not in self.ended_turn and ally.unit_id not in self.waiting

    def _check_may_act(self, ally):
        if self.phase != CombatPhase.PLAYER_TURN:
            raise RuntimeError("It is not the player turn.")
        if ally.unit_id in self.pending_choices:
            raise ValueError("Answer the choice in front of you first.")
        if not ally.is_alive():
            raise ValueError(f"{ally.unit_id} has been defeated and cannot act.")

    @staticmethod
    def _play_cap(ally):
        """The tightest cap on cards played this turn that the hand imposes,
        or a status (Ringing: one card).

        Hand only: Sloth and Normality stop you while you are holding them.
        Contrast _deck_penalties, which charges you wherever the card sits."""
        caps = [create_card(card_id).PLAY_CAP for card_id in ally.hand]
        caps += [status.PLAY_CAP for status in ally.statuses.values()]
        caps = [cap for cap in caps if cap is not None]
        return min(caps) if caps else None

    @classmethod
    def _capped(cls, ally):
        """Whether `ally` has played as many cards this turn as the cap allows.
        Plays started count, so a card Havoc turns up as your third play is
        already past Normality (the game counts CardPlaysStarted)."""
        cap = cls._play_cap(ally)
        return cap is not None and ally.turn_count("cards_started") >= cap

    @staticmethod
    def _forbidden(ally, card):
        """Whether a status of `ally`'s rules this card out (Smoggy)."""
        return any(status.forbids_play(card) for status in ally.statuses.values())

    @staticmethod
    def _deck_penalties(ally):
        """What this ally's deck costs them this turn, as (draw, energy).

        Counted across hand, draw pile and discard pile, because Mind Rot and
        Waste Away charge you for being in your deck, not for being in your
        hand. Exhausting one is the way out, which is why the exhaust pile is
        not counted. Copies stack."""
        draw = energy = 0
        for pile in (ally.hand, ally.draw_pile, ally.discard_pile):
            for card_id in pile:
                card = create_card(card_id)
                draw += card.DRAW_PENALTY
                energy += card.ENERGY_PENALTY
        return draw, energy

    def _turn_draw(self, ally):
        """Deal this ally's hand for the turn, after what their deck costs."""
        draw_penalty, energy_penalty = self._deck_penalties(ally)
        if energy_penalty:
            ally.energy = max(0, ally.energy - energy_penalty)
        return self._draw_cards(ally, max(0, self.HAND_SIZE - draw_penalty))

    @staticmethod
    def _must_play_first(ally):
        """The card in hand that has to be played before any other, or None.

        The first copy is the one that has to go, so two Enthralled come out
        in order rather than either satisfying the other."""
        for card_id in ally.hand:
            if create_card(card_id).MUST_PLAY_FIRST:
                return card_id
        return None

    def card_cost(self, ally, card):
        """What this card costs `ally` right now.

        The card's own clause runs first, then statuses, so Corruption can zero
        a Skill whatever it would otherwise cost. Statuses run in COST_ORDER:
        a free Attack is priced last, so Tangled's +1 cannot survive it - the
        game's "late" cost modifier.
        """
        if card.cost == Card.X_COST:
            return ally.energy
        cost = card.dynamic_cost(self._context_for(ally, ally))
        if card.cost_cap is not None:
            # A cap set on this copy (Enlightenment, a free copy at 0) only
            # ever lowers it; statuses come after, as the game's global
            # modifiers come after a card's local ones.
            cost = min(cost, card.cost_cap)
        for status in sorted(ally.statuses.values(), key=lambda s: s.COST_ORDER):
            cost = status.modify_card_cost(cost, card)
        return max(0, int(cost))

    def auto_play_card(self, ally, card_id, from_pile=None, target=None,
                       force_exhaust=False):
        """Play a card nobody chose: Havoc, Mayhem, Stampede, Hellraiser.

        No energy is paid and no target is asked for. An unplayable card is
        still lifted and routed - Havoc exhausts whatever it turns up.
        """
        if self._play_depth >= self.MAX_PLAY_DEPTH:
            return []
        card = create_card(card_id)

        if from_pile is not None and not take(from_pile, card_id):
            return []

        # The game's ShouldPlay is asked of an automatic play too: past
        # Normality's third card the card goes to its pile unplayed.
        if not card.properties.playable or self._forbidden(ally, card) or self._capped(ally):
            self._route_played(ally, card_id, card, force_exhaust)
            return []

        if target is None:
            resolvable, target = self._auto_target(card, ally)
            if not resolvable:
                # Nothing to hit, but it was still played.
                self._route_played(ally, card_id, card, force_exhaust)
                return []

        self._play_depth += 1
        try:
            # x_amount 0: nobody paid, so an auto-played X card does nothing.
            return self._play(ally, card_id, card, target, force_exhaust)
        finally:
            self._play_depth -= 1

    def _play(self, ally, card_id, card, target, force_exhaust=False,
              x_amount=0):
        """Resolve a card and put it away. Both play paths come through here.

        The card reaches its pile only after resolving, so a card that reads
        its own discard pile (Stack) does not count itself.
        """
        plays = 1 + self._extra_plays(ally, card, target)
        self._spend_on_play(ally, card)
        if getattr(card_id, "turn_cost_cap", None) is not None:
            # "This turn, or until played": played, the cap is gone.
            card_id.turn_cost_cap = None
        results = []
        exhausted = False

        for index in range(plays):
            self._play_serial += 1
            # Counted as it starts, as the game's CardPlaysStarted: what
            # Normality, Sloth and Ringing count (_capped).
            ally.turn_counters["cards_started"] = ally.turn_count("cards_started") + 1
            context = self._context_for(ally, target, x_amount=x_amount)
            context.played = card_id
            context.play_id = self._play_serial
            hits = _Hits()
            for effect in card.get_effects(context):
                self._stamp(effect, context.play_id)
                hits.mark(effect)
                result = self._resolve(effect)
                if result is None:
                    continue
                results.append(result)
                # Follow-ups are not offered back, so this cannot chain.
                for extra in card.follow_up(result, context) or ():
                    self._stamp(extra, context.play_id)
                    extra_result = self._resolve(extra)
                    if extra_result is not None:
                        results.append(extra_result)
            if index + 1 == plays:
                exhausted = self._route_played(ally, card_id, card, force_exhaust)
            # Emitted once per play, so a counter sees an extra play as a play.
            self._emit(GameEvent.CARD_PLAYED, ally, card=card)

        if exhausted:
            self._emit(GameEvent.CARD_EXHAUSTED, ally, card=card)

        self._check_combat_end()
        return results

    @staticmethod
    def _stamp(effect, play_id):
        """Mark an effect as part of card play `play_id`, if it is the kind
        that records one (InstantBlock) and has none yet."""
        if getattr(effect, "play_id", False) is None:
            effect.play_id = play_id

    def _route_played(self, ally, card_id, card, force_exhaust=False):
        """Put a played card away. True if it was exhausted.

        Powers go to no pile at all - they carry on as a status.
        """
        if force_exhaust or card.properties.exhaust:
            ally.exhaust_pile.append(card_id)
            return True
        if card.card_type is CardType.POWER:
            return False
        pile = self._redirect_pile(ally, card)
        if pile == InstantMoveCard.GONE:
            # Held out of play by a status that will bring it back: Bolas and
            # Thrumming Hatchet return to hand next turn.
            return False
        if pile == InstantMoveCard.EXHAUST:
            ally.exhaust_pile.append(card_id)
            return True
        if pile == InstantMoveCard.DRAW:
            ally.draw_pile.append(card_id)   # the top: drawn from the end
        else:
            ally.discard_pile.append(card_id)
        return False

    def _redirect_pile(self, ally, card):
        """Nostalgia and Rebound send a just-played card somewhere other than
        the discard pile. First status to claim it wins, and claiming is what
        spends the charge."""
        context = self._context_for(ally, ally)
        statuses = sorted(ally.statuses.values(), key=lambda s: s.REDIRECT_ORDER)
        for status in statuses:
            pile = status.redirect_played_card(card, context)
            if pile is not None:
                return pile
        return None

    def _extra_plays(self, ally, card, target):
        """How many extra times this card is played, spending the grants.

        Replay belongs to the copy and is never spent: a card with Replay 2
        resolves three times every time it is played, whatever type it is.
        One-Two Punch and Tag Team are one-shot, and only Attacks trigger
        either - Tag Team primes the enemy against somebody else's attack."""
        extra = card.replay
        if card.card_type is not CardType.ATTACK:
            return extra
        if self._spend_status(ally, "one_two_punch"):
            extra += 1
        # Tag Team: an Attack aimed at the marked enemy, or one that hits every
        # enemy - not a random one (the game's TagTeamPower). Each mark adds
        # its plays and is used up; the applier's own Attacks never set it off.
        if card.target_type is TargetType.ENEMY:
            marked = [target] if target is not None else []
        elif card.target_type is TargetType.ALL_ENEMIES:
            marked = [enemy for enemy in self.enemies if enemy.is_alive()]
        else:
            marked = []
        for enemy in marked:
            tag = enemy.get_status("tag_team")
            if tag is not None:
                extra += tag.spend(ally)
        return extra

    def _spend_on_play(self, ally, card):
        """One charge of a free Attack goes on every Attack played - from hand
        or auto-played, and even one that already cost 0, as in the game."""
        if card.card_type is CardType.ATTACK:
            self._spend_status(ally, "free_attack")

    @staticmethod
    def _spend_status(unit, effect_id):
        """Take one charge off a counter status. True if there was one."""
        status = unit.get_status(effect_id)
        if status is None or status.amount <= 0:
            return False
        status.amount -= 1
        if status.amount <= 0:
            unit.remove_status(effect_id)
        return True

    def _auto_target(self, card, ally):
        """Who a card played by another card hits, as (resolvable, target).

        Nobody is asked, so an enemy-targeting card picks a random living
        enemy, as the game's CardCmd.AutoPlay does. False means there is
        nothing left for it to hit."""
        target_type = card.target_type

        if target_type is TargetType.SELF:
            return True, ally
        if target_type in (TargetType.ALL_ENEMIES, TargetType.ALL_ALLIES):
            return True, None

        if target_type in (TargetType.ENEMY, TargetType.RANDOM_ENEMY):
            living = [e for e in self.enemies if e.is_alive()]
            if not living:
                return False, None
            return True, self.rngs.targets.choice(living)

        living = [a for a in self.allies if a.is_alive()]
        if not living:
            return False, None
        others = [a for a in living if a is not ally]
        if target_type is TargetType.ALLY and not others:
            # "Another player", and there is nobody: Havoc turning up
            # Coordinate in a solo fight has nothing to aim it at.
            return False, None
        return True, self.rngs.targets.choice(others or living)

    def end_player_turn(self):
        if self.phase != CombatPhase.PLAYER_TURN:
            raise RuntimeError("It is not the player turn.")
        if self.pending_choices:
            waiting = ", ".join(sorted(self.pending_choices))
            raise RuntimeError(f"Still waiting on a choice from {waiting}.")

        self.ended_turn.clear()
        self.waiting.clear()
        self._tick_statuses(self.allies)

        # After the tick, or a status applied here (Doubt) is stripped the
        # instant it lands. Before the discard, because the cards must be held.
        for ally in self.allies:
            if ally.is_alive():
                self._play_from_exhaust(ally)
                self._emit(GameEvent.TURN_END, ally)
        if self._check_combat_end():
            return               # Howl from Beyond can finish the fight here

        self._discard_hands()
        for ally in self.allies:
            # A cost set "this turn" (Enlightenment) lapses, wherever the copy is.
            for pile in (ally.hand, ally.draw_pile, ally.discard_pile, ally.exhaust_pile):
                for ref in pile:
                    if getattr(ref, "turn_cost_cap", None) is not None:
                        ref.turn_cost_cap = None

        self.phase = CombatPhase.ENEMY_TURN
        self._run_enemy_turn()
        if self.is_over():
            return
        # The game's AfterSideTurnEnd for the enemy side: Territorial.
        self._emit(GameEvent.ENEMY_TURN_END)
        if self._check_combat_end():
            return

        self._tick_statuses(self.enemies)
        self._tick_statuses(self.allies, after_enemy_turn=True)
        self._new_turn()
        self._revive_due()
        for enemy in self.enemies:
            if enemy.is_alive():
                enemy.choose_intent(self._context_for(enemy))

        self.phase = CombatPhase.PLAYER_TURN
        # A new player turn: "this turn" starts counting again for everyone.
        for unit in self.allies + self.enemies:
            unit.reset_turn_counters()
        for ally in self.allies:
            if ally.is_alive():
                ally.start_turn()
                # Hello World's card and a returning Bolas arrive first, so
                # they take hand room and are not drawn (the game's BeforeHandDraw).
                self._emit(GameEvent.BEFORE_HAND_DRAW, ally)
                self._turn_draw(ally)
                self._emit(GameEvent.TURN_START, ally)
        self._drain_asks()

    # --- serialization -------------------------------------------------------

    def to_dict(self):
        return {
            "phase": self.phase.name,
            "result": self.result.name if self.result is not None else None,
            "allies": [self._ally_dict(ally) for ally in self.allies],
            "enemies": [self._enemy_dict(enemy) for enemy in self.enemies],
            # Whoever is being asked something, and what the options are.
            "choices": {unit_id: ask.to_dict()
                        for unit_id, ask in self.pending_choices.items()},
        }

    def _ally_dict(self, ally):
        """An ally as the players see it, plus `hand_cost` and `hand_damage`
        for the cards in hand. Worked out as the state is sent, like an
        intent's damage, so they follow Stomp's discount, a Tangled, or
        Strength gained mid-turn."""
        data = ally.to_dict()
        data["hand_cost"] = self.hand_costs(ally)
        data["hand_damage"] = self.hand_damages(ally)
        # What each card in hand does, numbers filled in for this copy - an
        # Attack's damage after this ally's Strength, Weak and Vigor, and the
        # Block it gives after their Dexterity and Frail.
        blocks = self.hand_blocks(ally)
        data["hand_text"] = [card_text(create_card(c), ally, blocks[i])
                             for i, c in enumerate(ally.hand)]
        data["piles"] = self.pile_view(ally)
        # Every play, end turn, wait or answer they may send now: the mask an
        # agent picks from, and what an analyzer compares a choice against.
        data["legal_actions"] = self.legal_actions(ally)
        data["ended_turn"] = ally.unit_id in self.ended_turn
        data["waiting"] = ally.unit_id in self.waiting
        return data

    def hand_blocks(self, ally):
        """Per card in hand, the Block it gives this ally when played: after
        their Dexterity, Frail, Unmovable and Fasten, as the game shows it.
        None for a card that gives them no Block (Lift's goes to a teammate;
        Mimic's depends on the target, not chosen yet).

        Each card is lifted out of the hand while it is worked out and put
        back, because that is where it is when it plays - Second Wind counts
        the other cards, not itself. A card that gains several times (Second
        Wind) is added up gain by gain, all as one play not yet made: Unmovable
        doubles every gain of a play or none, by the gains already this turn.
        Nothing is changed."""
        blocks = []
        for index in range(len(ally.hand)):
            card_id = ally.hand.pop(index)
            try:
                gains = create_card(card_id).block_gains(ally)
                total = None
                if gains is not None:
                    total = sum(Resolver.block_amount(ally, amount, powered, True, ally,
                                                      self._NEXT_PLAY)
                                for amount, powered in gains)
            finally:
                ally.hand.insert(index, card_id)
            blocks.append(total)
        return blocks

    # The play a card in hand would be: a number no play on record has.
    _NEXT_PLAY = object()

    # The game lists Status and Curse cards after every rarity.
    _PILE_LAST = {CardType.STATUS: 100, CardType.CURSE: 101}

    def pile_view(self, ally):
        """The draw, discard and exhaust piles as a player may look at them:
        one {"id", "upgraded", "text"} per card. The draw pile is sorted by
        rarity then id, as the game's pile screen sorts it, so its order -
        which card comes next - is not given away. Discard and exhaust keep
        their order, newest last."""
        def entry(card_id):
            return {"id": str(card_id), "upgraded": is_upgraded(card_id),
                    "text": card_text(create_card(card_id))}

        def draw_order(card_id):
            card = create_card(card_id)
            return (self._PILE_LAST.get(card.card_type, card.rarity.value),
                    str(card_id), is_upgraded(card_id))

        return {
            "draw": [entry(c) for c in sorted(ally.draw_pile, key=draw_order)],
            "discard": [entry(c) for c in ally.discard_pile],
            "exhaust": [entry(c) for c in ally.exhaust_pile],
        }

    def hand_damages(self, ally):
        """Per card in hand, the damage one hit deals as the game shows it
        before a target is chosen: after this ally's Strength, Weak and Vigor,
        not the target's Vulnerable. None for a card that is not an Attack."""
        damages = []
        for card_id in ally.hand:
            base = create_card(card_id).base_damage(ally)
            damages.append(None if base is None
                           else Resolver.damage_amount(ally, None, base))
        return damages

    def hand_costs(self, ally):
        """Per card in hand, the cost the game prints on it right now: a
        number, "X" for an X-cost card, or None for one that cannot be played.
        A free copy (Infernal Blade, Distraction) shows 0, or more under
        Tangled, as play_card charges it."""
        costs = []
        for card_id in ally.hand:
            card = create_card(card_id)
            if not card.properties.playable:
                costs.append(None)
            elif card.cost == Card.X_COST:
                costs.append(Card.X_COST)
            else:
                costs.append(self.card_cost(ally, card))
        return costs

    def legal_actions(self, ally):
        """Everything `ally` may do right now, each shaped like the message
        that does it: {"type": "play_card", "hand_index", "target_id"},
        {"type": "end_turn"}, {"type": "wait"} (may_wait), and
        {"type": "choose", "option_index"} - STOP (-1) for an "up to N"
        question. The checks are play_card's, in its order, so an action
        listed is accepted and any other is refused.

        A card that picks its own target (Self, All, Random) is one action
        with target_id None; one sent anyway is ignored. Nothing is rolled:
        a random target is drawn when the card is played, not here."""
        if self.phase != CombatPhase.PLAYER_TURN:
            return []
        ask = self.pending_choices.get(ally.unit_id)
        if ask is not None:
            actions = [{"type": "choose", "option_index": i} for i in range(len(ask.options))]
            if ask.can_stop:
                actions.append({"type": "choose", "option_index": PendingChoice.STOP})
            return actions
        if not ally.is_alive():
            return []

        actions = []
        if not self._capped(ally):
            locked = self._must_play_first(ally)
            for index, card_id in enumerate(ally.hand):
                card = create_card(card_id)
                if not card.properties.playable:
                    continue
                if locked is not None and locked is not card_id:
                    continue
                if not card.playable_now(ally) or self._forbidden(ally, card):
                    continue
                if ally.energy < self.card_cost(ally, card):
                    continue
                actions.extend({"type": "play_card", "hand_index": index, "target_id": target_id}
                               for target_id in self._legal_targets(card, ally))
        actions.append({"type": "end_turn"})
        if self.may_wait(ally):
            actions.append({"type": "wait"})
        return actions

    def _legal_targets(self, card, ally):
        """The target_ids _resolve_target accepts for this card."""
        target_type = card.target_type
        if target_type == TargetType.ENEMY:
            return [enemy.unit_id for enemy in self.enemies if enemy.is_alive()]
        if target_type == TargetType.ALLY:
            return [other.unit_id for other in self.allies
                    if other is not ally and other.is_alive()]
        if target_type == TargetType.RANDOM_ENEMY:
            return [None] if any(enemy.is_alive() for enemy in self.enemies) else []
        if target_type == TargetType.RANDOM_ALLY:
            return [None] if any(other.is_alive() for other in self.allies) else []
        if target_type in (TargetType.SELF, TargetType.ALL_ENEMIES, TargetType.ALL_ALLIES):
            return [None]
        return []

    def _enemy_dict(self, enemy):
        """An enemy as the players see it. An attack intent also carries, per
        living player, the damage one hit will do to them - after the enemy's
        Strength and Weak and that player's Vulnerable, as the game shows it.
        Worked out now rather than when the intent was chosen, so it moves
        when a player Weakens the enemy mid-turn."""
        data = enemy.to_dict()
        intent = data.get("intent")
        stun = enemy.get_status("stun")
        if enemy.is_alive() and stun is not None and stun.amount > 0:
            # What it will do is nothing: the game swaps in a Stunned move.
            data["intent"] = {"type": "stun", "name": "Stunned", "amount": 0, "hits": 1, "block": 0}
            return data
        if isinstance(intent, dict) and intent.get("type") == "attack":
            intent = dict(intent)          # never write into the enemy's own
            intent["damage"] = {
                ally.unit_id: Resolver.damage_amount(enemy, ally, intent.get("amount", 0))
                for ally in self.allies if ally.is_alive()
            }
            data["intent"] = intent
        return data

    # --- internals -------------------------------------------------------

    def _context_for(self, source, target=None, payload=None, x_amount=0):
        return Context(
            source=source,
            target=target,
            all_allies=self.allies,
            all_enemies=self.enemies,
            rng=self.rng,
            rngs=self.rngs,
            payload=payload,
            counters=self.combat_counters,
            x_amount=x_amount,
            asks=self._asks,
        )

    # --- choices -----------------------------------------------------------

    def _drain_asks(self):
        """Answer the questions this action raised, and return what they did.

        Each player holds one question at a time; the rest of theirs wait in
        order behind it, so a card's questions arrive in the order it asked.
        A waiting question's options are not read until it is put, because
        the answer before it may change them.
        """
        results = []
        waiting = []
        for ask in self._asks:
            unit_id = ask.ally.unit_id
            if not self.ask_players or unit_id in self.unattended:
                if ask.options:
                    results.extend(
                        self._apply_choice(ask, self.rngs.answers.choice(ask.options)))
            elif unit_id in self.pending_choices:
                waiting.append(ask)
            elif ask.options:
                self.pending_choices[unit_id] = ask
            # else: the answer before it left nothing to pick
        # In place: every Context already handed out holds this very list, and
        # a callback answering one question may append the next to it.
        self._asks[:] = waiting
        self._check_combat_end()
        return results

    def _apply_choice(self, ask, chosen):
        results = []
        for effect in ask.resolve(chosen) or ():
            self._stamp(effect, ask.play_id)
            result = self._resolve(effect)
            if result is not None:
                results.append(result)
        return results

    def answer_choice(self, ally, option_index):
        """Carry out the option this player picked, then ask what comes next.

        PendingChoice.STOP ends an "up to N" question with nothing picked.
        Its answer is never resolved, so the card asks nothing further."""
        ask = self.pending_choices.get(ally.unit_id)
        if ask is None:
            raise ValueError(f"{ally.unit_id} has nothing to choose.")
        if option_index == PendingChoice.STOP:
            if not ask.can_stop:
                raise ValueError("This question needs an answer; it cannot be stopped.")
            del self.pending_choices[ally.unit_id]
            self.waiting.clear()
            return self._drain_asks()
        if not (0 <= option_index < len(ask.options)):
            raise IndexError(f"option_index {option_index} out of range.")

        del self.pending_choices[ally.unit_id]
        self.waiting.clear()
        results = self._apply_choice(ask, ask.options[option_index])
        results.extend(self._drain_asks())
        return results

    def choice_for(self, ally):
        return self.pending_choices.get(ally.unit_id)

    def forfeit_choices(self, ally):
        """A player has left: answer what they were asked, and whatever they
        are asked from now on, at random."""
        self.unattended.add(ally.unit_id)
        self.waiting.clear()       # whoever waited on them looks again
        results = []
        ask = self.pending_choices.pop(ally.unit_id, None)
        if ask is not None:
            results.extend(self._apply_choice(ask, self.rngs.answers.choice(ask.options)))
        results.extend(self._drain_asks())
        return results

    # --- events -----------------------------------------------------------

    def _resolve(self, effect):
        # The two effects Resolver cannot own: a card play needs the play
        # pipeline, a summon the rng, the scaling and the unit ids.
        if isinstance(effect, InstantPlayCard):
            return self._resolve_play_card(effect)
        if isinstance(effect, InstantSummon):
            return self._resolve_summon(effect)
        result = Resolver.resolve(effect)
        if result is not None:
            self._emit_for(effect, result)
        return result

    def _resolve_play_card(self, effect):
        ally = effect.target
        if effect.card_id is None:
            results = self._play_from_top(ally, effect.count, effect.force_exhaust)
        else:
            pile = getattr(ally, effect.from_pile) if effect.from_pile else None
            results = self.auto_play_card(
                ally, effect.card_id, from_pile=pile, target=effect.at,
                force_exhaust=effect.force_exhaust)
        # auto_play_card has already emitted everything.
        return {
            "effect_id": effect.effect_id,
            "source_id": effect.source.unit_id,
            "target_id": ally.unit_id,
            "card_id": effect.card_id,
            "amount": len(results),
            "results": results,
        }

    def _play_from_top(self, ally, count, force_exhaust):
        """Play the top `count` cards of the draw pile (Havoc, Cascade).

        As the game's AutoPlayFromDrawPile: the discard is shuffled in
        whenever the draw pile runs dry, all the cards are lifted first, and
        then each is played. Lifting first means a card that draws cannot
        pull one of the others into the hand."""
        if self._play_depth >= self.MAX_PLAY_DEPTH:
            return []
        lifted = []
        for _ in range(count):
            if not ally.reshuffle_if_empty(self.rngs.shuffle):
                break
            self._drain_shuffles(ally)
            lifted.append(ally.draw_pile.pop())      # drawn from the end
        results = []
        for index, card_id in enumerate(lifted):
            if self.is_over() or not ally.is_alive():
                # Nothing left to play them into; they are discarded, not lost.
                ally.discard_pile.extend(lifted[index:])
                break
            results.extend(self.auto_play_card(ally, card_id, force_exhaust=force_exhaust))
        return results

    def _play_from_exhaust(self, ally):
        """At the end of the turn, a card that says so plays itself out of the
        exhaust pile (Howl from Beyond). Not forced to exhaust again, so it
        goes to the discard pile afterwards - it comes back only if something
        exhausts it again."""
        for card_id in list(ally.exhaust_pile):
            if self.is_over() or not ally.is_alive():
                return
            if create_card(card_id).PLAYS_FROM_EXHAUST_AT_TURN_END:
                self.auto_play_card(ally, card_id, from_pile=ally.exhaust_pile)

    def _emit_for(self, effect, result):
        eid = result["effect_id"]
        target = effect.target

        if eid in ("instant_draw", "instant_draw_until"):
            # Before CARD_DRAWN: the shuffle happened during the draw, and
            # Stratagem takes from the pile it produced.
            self._drain_shuffles(target)

        if eid == "instant_damage":
            # Non-attack damage still costs HP, but nothing reacts to it
            # as an attack.
            if effect.is_attack:
                self._emit(GameEvent.ATTACKED, target,
                           amount=result["amount"], attacker=effect.source,
                           hit=getattr(effect, "hit", None))
            if result["amount"] > 0:
                self._emit(GameEvent.HP_LOST, target, amount=result["amount"])
        elif eid == "instant_hp_loss":
            if result["amount"] > 0:
                self._emit(GameEvent.HP_LOST, target, amount=result["amount"])
        elif eid == "instant_block":
            if result["amount"] > 0:
                self._emit(GameEvent.BLOCK_GAINED, target, amount=result["amount"],
                           beacons=getattr(effect, "beacons", ()))
        elif eid == "instant_exhaust":
            for card_id in result["card_ids"]:
                self._emit(GameEvent.CARD_EXHAUSTED, target, card=create_card(card_id))
        elif eid in ("instant_draw", "instant_draw_until"):
            if result["amount"] > 0:
                self._emit(GameEvent.CARD_DRAWN, target,
                           amount=result["amount"], card_ids=result["card_ids"])
        elif result.get("blocked_by"):
            pass                 # Artifact stopped it: nothing was applied
        elif not eid.startswith("instant_"):
            # What is left is a status. Matched on the name so a new instant
            # effect cannot be announced as one by forgetting a list.
            self._emit(GameEvent.STATUS_APPLIED, target,
                       effect_id=eid, applied_by=effect.source)

    def _emit(self, event, subject=None, **payload):
        if self._event_depth >= self.MAX_EVENT_DEPTH:
            return []

        key = self.COUNTED_EVENTS.get(event)
        if key is not None and subject is not None:
            step = payload.get("amount", 1)
            subject.turn_counters[key] = subject.turn_count(key) + step

        key = self.COMBAT_COUNTED_EVENTS.get(event)
        if key is not None and subject is not None:
            subject.combat_counters[key] = subject.combat_count(key) + 1

        if event is GameEvent.ATTACKED and subject is not None:
            # One entry per hit, as the game's DamageReceivedEntry: Gang Up
            # pays for every hit a teammate landed, a Twin Strike twice.
            attacker = payload.get("attacker")
            if attacker is not None:
                subject.turn_counters.setdefault("attacked_by", []).append(attacker)

        if event is GameEvent.CARD_EXHAUSTED:
            # By anyone, for a card that counts every exhaust in the fight.
            self.combat_counters["cards_exhausted"] = (
                self.combat_counters.get("cards_exhausted", 0) + 1)

        if event is GameEvent.CARD_PLAYED and subject is not None:
            # Juggling and Stomp count Attacks, not cards; Smoggy, Skills.
            played = payload.get("card")
            if played is not None and played.card_type is CardType.ATTACK:
                subject.turn_counters["attacks_played"] = (
                    subject.turn_count("attacks_played") + 1)
            if played is not None and played.card_type is CardType.SKILL:
                subject.turn_counters["skills_played"] = (
                    subject.turn_count("skills_played") + 1)
            # By anyone on the team, kept on every player so a card in hand
            # can read it: Gold Axe counts each card played in the fight (the
            # game's CardPlaysFinished).
            for ally in self.allies:
                ally.combat_counters["team_cards_played"] = (
                    ally.combat_count("team_cards_played") + 1)

        payload["phase"] = self.phase.name
        produced = []
        for unit in self.allies + self.enemies:
            if not unit.is_alive():
                continue
            for status in list(unit.statuses.values()):
                out = status.on_event(event, self._context_for(unit, subject, payload))
                if out:
                    produced.extend(out)

        card = payload.get("card")
        if event is GameEvent.CARD_EXHAUSTED and card is not None and subject is not None:
            out = card.on_event(event, self._context_for(subject, subject, payload))
            if out:
                produced.extend(out)

        if event is GameEvent.CARD_DRAWN and subject is not None:
            # Only the drawn cards react, once each - walking the hand would
            # fire every Void already held.
            for card_id in payload.get("card_ids", ()):
                out = create_card(card_id).on_event(
                    event, self._context_for(subject, subject, payload))
                if out:
                    produced.extend(out)
        elif event in self.HAND_EVENTS and subject in self.allies and subject.is_alive():
            # Only the hand of the player whose turn is ending. TURN_END is
            # emitted once per ally, so walking every hand here fired a Burn
            # once per player in the fight: 2 damage solo, 4 in a duo.
            for card_id in list(subject.hand):
                card = create_card(card_id)
                out = card.on_event(
                    event, self._context_for(subject, subject, payload))
                if out:
                    produced.extend(out)

        self._event_depth += 1
        try:
            for eff in produced:
                self._resolve(eff)
        finally:
            self._event_depth -= 1
        return produced

    def _resolve_target(self, card, ally, target):
        target_type = card.target_type

        if target_type == TargetType.SELF:
            return ally

        if target_type == TargetType.ENEMY:
            return self._validated_target(card, target, self.enemies, "enemy")

        if target_type == TargetType.ALLY:
            target = self._validated_target(card, target, self.allies, "ally")
            # Every ALLY-target card says "another player". Refused here, before
            # the cost is paid - a card that refused from inside get_effects
            # had already left the hand and taken the energy with it.
            if target is ally:
                raise ValueError(f"{card.name} must target another player.")
            return target

        if target_type in (TargetType.ALL_ENEMIES, TargetType.ALL_ALLIES):
            return None

        if target_type == TargetType.RANDOM_ENEMY:
            return self._random_living_target(card, self.enemies)

        if target_type == TargetType.RANDOM_ALLY:
            return self._random_living_target(card, self.allies)

        raise ValueError(
            f"{card.name} has an unhandled target type: {target_type.name}"
        )

    @staticmethod
    def _validated_target(card, target, pool, noun):
        if target is None:
            raise ValueError(f"{card.name} requires a target.")
        if target not in pool:
            raise ValueError(f"{target.unit_id} is not a valid {noun} target.")
        if not target.is_alive():
            raise ValueError(f"{target.unit_id} has already been defeated.")
        return target

    def _random_living_target(self, card, pool):
        living = [unit for unit in pool if unit.is_alive()]
        if not living:
            raise ValueError(f"{card.name} has no living target available.")
        return self.rngs.targets.choice(living)

    def _run_enemy_turn(self):
        # The enemy side's turn begins: Sandpit counts down here, as in the
        # game, so a player gets their whole turn before it bites.
        self._emit(GameEvent.ENEMY_TURN_START)
        if self._check_combat_end():
            return
        # A snapshot, as the game walks `Enemies.ToList()`: an enemy summoned
        # during the phase (Fogmog's Eye) waits for the next one to act.
        for enemy in list(self.enemies):
            if not enemy.is_alive():
                continue
            stun = enemy.get_status("stun")
            if stun is not None and stun.amount > 0:
                # The whole turn goes, block clearing included. Counted down
                # here so a stun applied mid-turn is not spent before it lands.
                # The move it had lined up is put off, not lost: the game's
                # stunned move hands back to it (CreatureCmd.Stun).
                stun.amount -= 1
                enemy.skipped_move = True
                continue
            enemy.clear_block()
            # No target: every move lands on every player (see _scripted.Move).
            context = self._context_for(enemy)
            hits = _Hits()
            for effect in enemy.get_effects(context):
                self._intercept(effect)
                hits.mark(effect)
                self._resolve(effect)
            if self._check_combat_end():
                return

    def _intercept(self, effect):
        """Point an enemy attack at whoever is intercepting for its target.

        Before resolving, so the interceptor's own Block and Vulnerable are
        what the hit meets, and their Flame Barrier is what answers it. Only
        attacks: Intercept covers being hit, not being cursed.
        """
        if not isinstance(effect, InstantDamage) or not effect.is_attack:
            return
        victim = effect.target
        if victim not in self.allies or not victim.is_alive():
            return
        for ally in self.allies:
            if ally is victim or not ally.is_alive():
                continue
            covering = ally.get_status("intercepting")
            if covering is not None and covering.amount > 0 and victim in covering.covered:
                effect.target = ally
                return

    def _tick_statuses(self, units, after_enemy_turn=False):
        """Count statuses down. Players' statuses are counted at the end of
        their own turn, except Vulnerable / Weak / Frail, which wait for the
        end of the enemy turn (`after_enemy_turn`); enemies' at the end of
        theirs. A status flagged skip_next_tick sits one count-down out."""
        for unit in units:
            if not unit.is_alive():
                continue
            is_player = unit in self.allies
            for status in list(unit.statuses.values()):
                if is_player and status.TICKS_AFTER_ENEMY_TURN != after_enemy_turn:
                    continue
                if status.TICKS_AFTER_ENEMY_TURN and status.skip_next_tick:
                    status.skip_next_tick = False
                    continue
                status.on_owner_turn_end()
                if status.is_expired():
                    unit.remove_status(status.effect_id)

    def _discard_hands(self):
        for ally in self.allies:
            if ally.retain_hand:
                continue  # the whole hand carries over this turn
            kept = []
            for card_id in ally.hand:
                properties = create_card(card_id).properties
                if properties.ethereal:
                    # Ethereal cards exhaust rather than discard.
                    ally.exhaust_pile.append(card_id)
                    self._emit(GameEvent.CARD_EXHAUSTED, ally, card=create_card(card_id))
                elif properties.retain:
                    kept.append(card_id)
                else:
                    ally.discard_pile.append(card_id)
            ally.hand = kept

    def _build_draw_pile(self, ally):
        # A fresh copy of every card in the deck. Copies rather than the deck
        # entries themselves, which is what scopes an upgrade to the combat -
        # and lets a deck hold a card that is permanently upgraded.
        ally.draw_pile = [new_ref(card_id) for card_id in ally.deck]
        self.rngs.shuffle.shuffle(ally.draw_pile)
        # Innate first. The pile is drawn from the end, so they go last.
        # Partitioned rather than filtered, because Innate can be one copy's
        # upgrade: two Aggressions need not answer the same way.
        innate, rest = [], []
        for card_id in ally.draw_pile:
            bucket = innate if create_card(card_id).properties.innate else rest
            bucket.append(card_id)
        ally.draw_pile = rest + innate

    def _drain_shuffles(self, ally):
        """Announce any reshuffle the draw just did.

        An Ally has no Combat to emit with, so it counts them and this reports
        them. Drained after the draw finishes, never mid-loop, so a status that
        reacts cannot move a card out from under it."""
        pending = getattr(ally, "shuffles_pending", 0)
        if not pending:
            return
        ally.shuffles_pending = 0
        for _ in range(pending):
            self._emit(GameEvent.DECK_SHUFFLED, ally)

    def _draw_cards(self, ally, count):
        drawn = ally.draw(count, self.rngs.shuffle)
        self._drain_shuffles(ally)
        # The opening hand and every turn's hand are draws too, and are
        # where most draws happen.
        if drawn:
            self._emit(GameEvent.CARD_DRAWN, ally, amount=len(drawn),
                       card_ids=drawn)
        return drawn

    def _check_combat_end(self):
        # Deaths first: one can bring enemies in (Phrog Parasite's Wrigglers,
        # the Gremlin Merc's gremlins) or take Minions out with their leader,
        # and the others may react (Corpse Slug's Ravenous).
        self._resolve_deaths()
        if not any(enemy.is_alive() for enemy in self.enemies):
            self.phase = CombatPhase.OVER
            self.result = CombatResult.VICTORY
            return True
        if not any(ally.is_alive() for ally in self.allies):
            self.phase = CombatPhase.OVER
            self.result = CombatResult.DEFEAT
            return True
        return False
