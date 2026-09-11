import random
from enum import Enum

from ..Context.context import Context
from ..Events.game_event import GameEvent
from ..Resolution.resolver import Resolver
from ..Registry.card_registry import create_card
from ..Cards._card import Card
from ..Cards._card_enums import CardType, TargetType
from ..Cards._card_ref import new_ref, take
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_move_card import InstantMoveCard
from ..Effects.InstantEffects.instant_play_card import InstantPlayCard


class CombatPhase(Enum):
    NOT_STARTED = "NOT_STARTED"
    PLAYER_TURN = "PLAYER_TURN"
    ENEMY_TURN = "ENEMY_TURN"
    OVER = "OVER"


class CombatResult(Enum):
    VICTORY = "VICTORY"
    DEFEAT = "DEFEAT"


class Combat:
    HAND_SIZE = 5
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

    def __init__(self, allies, enemies, rng=None):
        self.allies = list(allies)
        self.enemies = list(enemies)
        self.rng = rng if rng is not None else random.Random()

        self.phase = CombatPhase.NOT_STARTED
        self.result = None
        self._event_depth = 0
        self._play_depth = 0
        # Whole-fight tallies belonging to no unit: Midnight's "by ANYONE".
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

    # --- lifecycle -------------------------------------------------------

    def start(self):
        for ally in self.allies:
            self._build_draw_pile(ally)
            self._turn_draw(ally)

        for enemy in self.enemies:
            enemy.choose_intent(self._context_for(enemy))

        self.phase = CombatPhase.PLAYER_TURN
        for unit in self.allies + self.enemies:
            unit.reset_turn_counters()
        for ally in self.allies:
            self._emit(GameEvent.TURN_START, ally)

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
        # the hand forbids must not spend energy or a free grant.
        cap = self._play_cap(ally)
        if cap is not None and ally.turn_count("cards_played") >= cap:
            raise ValueError(
                f"{ally.unit_id} cannot play more than {cap} cards this turn.")
        locked = self._must_play_first(ally)
        if locked is not None and locked is not card_id:
            raise ValueError(f"{create_card(locked).name} must be played first.")
        if not card.playable_now(ally):
            raise ValueError(f"{card.name} cannot be played out of this hand.")

        # Not spent yet: a rejected play must not burn a free grant.
        free_bucket = self._free_bucket(ally, card_id)
        cost = 0 if free_bucket is not None else self.card_cost(ally, card)
        free_attack = (
            free_bucket is None and cost > 0
            and card.card_type is CardType.ATTACK
            and ally.free_next_attack > 0)
        if free_attack:
            cost = 0
        if ally.energy < cost:
            raise ValueError(f"Not enough energy to play {card.name}.")

        resolved_target = self._resolve_target(card, ally, target)

        ally.spend_energy(cost)
        if free_bucket is not None:
            free_bucket.remove(card_id)
        if free_attack:
            ally.free_next_attack -= 1
        ally.hand.pop(hand_index)

        # An X-cost card spends everything, and needs to be told how much.
        x_amount = cost if card.cost == Card.X_COST else 0
        results = self._play(ally, card_id, card, resolved_target,
                             x_amount=x_amount)
        results.extend(self._drain_asks())
        return results

    @staticmethod
    def _play_cap(ally):
        """The tightest cap on cards played this turn that the hand imposes.

        Hand only: Sloth and Normality stop you while you are holding them.
        Contrast _deck_penalties, which charges you wherever the card sits."""
        caps = [create_card(card_id).PLAY_CAP for card_id in ally.hand]
        caps = [cap for cap in caps if cap is not None]
        return min(caps) if caps else None

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
        """What this card costs `ally` right now, before any free grant.

        The card's own clause runs first, then statuses, so Corruption can zero
        a Skill whatever it would otherwise cost.
        """
        if card.cost == Card.X_COST:
            return ally.energy
        cost = card.dynamic_cost(self._context_for(ally, ally))
        for status in list(ally.statuses.values()):
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

        if not card.properties.playable:
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
        results = []
        exhausted = False

        for index in range(plays):
            context = self._context_for(ally, target, x_amount=x_amount)
            for effect in card.get_effects(context):
                result = self._resolve(effect)
                if result is None:
                    continue
                results.append(result)
                # Follow-ups are not offered back, so this cannot chain.
                for extra in card.follow_up(result, context) or ():
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
        if ally.extra_attack_plays > 0:
            ally.extra_attack_plays -= 1
            extra += 1
        tag = target.get_status("tag_team") if target is not None else None
        if tag is not None and tag.amount > 0 and tag.source is not ally:
            tag.amount -= 1
            extra += 1
        return extra

    def _auto_target(self, card, ally):
        """Who a card played by another card hits, as (resolvable, target).

        Nobody is asked, so an enemy-targeting card takes the weakest living
        enemy - the reference engine's choice, and the one that wastes the
        least damage. False means there is nothing left for it to hit."""
        target_type = card.target_type

        if target_type is TargetType.SELF:
            return True, ally
        if target_type in (TargetType.ALL_ENEMIES, TargetType.ALL_ALLIES):
            return True, None

        if target_type in (TargetType.ENEMY, TargetType.RANDOM_ENEMY):
            living = [e for e in self.enemies if e.is_alive()]
            if not living:
                return False, None
            if target_type is TargetType.RANDOM_ENEMY:
                return True, self.rng.choice(living)
            return True, min(living, key=lambda e: e.current_hp)

        living = [a for a in self.allies if a.is_alive()]
        if not living:
            return False, None
        others = [a for a in living if a is not ally]
        return True, self.rng.choice(others or living)

    def end_player_turn(self):
        if self.phase != CombatPhase.PLAYER_TURN:
            raise RuntimeError("It is not the player turn.")
        if self.pending_choices:
            waiting = ", ".join(sorted(self.pending_choices))
            raise RuntimeError(f"Still waiting on a choice from {waiting}.")

        self._tick_statuses(self.allies)

        # After the tick, or a status applied here (Doubt) is stripped the
        # instant it lands. Before the discard, because the cards must be held.
        for ally in self.allies:
            if ally.is_alive():
                self._emit(GameEvent.TURN_END, ally)

        self._discard_hands()

        self.phase = CombatPhase.ENEMY_TURN
        self._run_enemy_turn()
        if self.is_over():
            return

        self._tick_statuses(self.enemies)
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
                self._turn_draw(ally)
                self._emit(GameEvent.TURN_START, ally)
        self._drain_asks()

    # --- serialization -------------------------------------------------------

    def to_dict(self):
        return {
            "phase": self.phase.name,
            "result": self.result.name if self.result is not None else None,
            "allies": [ally.to_dict() for ally in self.allies],
            "enemies": [enemy.to_dict() for enemy in self.enemies],
            # Whoever is being asked something, and what the options are.
            "choices": {unit_id: ask.to_dict()
                        for unit_id, ask in self.pending_choices.items()},
        }

    # --- internals -------------------------------------------------------

    def _context_for(self, source, target=None, payload=None, x_amount=0):
        return Context(
            source=source,
            target=target,
            all_allies=self.allies,
            all_enemies=self.enemies,
            rng=self.rng,
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
                        self._apply_choice(ask, self.rng.choice(ask.options)))
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
            result = self._resolve(effect)
            if result is not None:
                results.append(result)
        return results

    def answer_choice(self, ally, option_index):
        """Carry out the option this player picked, then ask what comes next."""
        ask = self.pending_choices.get(ally.unit_id)
        if ask is None:
            raise ValueError(f"{ally.unit_id} has nothing to choose.")
        if not (0 <= option_index < len(ask.options)):
            raise IndexError(f"option_index {option_index} out of range.")

        del self.pending_choices[ally.unit_id]
        results = self._apply_choice(ask, ask.options[option_index])
        results.extend(self._drain_asks())
        return results

    def choice_for(self, ally):
        return self.pending_choices.get(ally.unit_id)

    def forfeit_choices(self, ally):
        """A player has left: answer what they were asked, and whatever they
        are asked from now on, at random."""
        self.unattended.add(ally.unit_id)
        results = []
        ask = self.pending_choices.pop(ally.unit_id, None)
        if ask is not None:
            results.extend(self._apply_choice(ask, self.rng.choice(ask.options)))
        results.extend(self._drain_asks())
        return results

    # --- events -----------------------------------------------------------

    def _resolve(self, effect):
        # The one effect Resolver cannot own: it needs the play pipeline.
        if isinstance(effect, InstantPlayCard):
            return self._resolve_play_card(effect)
        result = Resolver.resolve(effect)
        if result is not None:
            self._emit_for(effect, result)
        return result

    def _resolve_play_card(self, effect):
        ally = effect.target
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
                           amount=result["amount"], attacker=effect.source)
            if result["amount"] > 0:
                self._emit(GameEvent.HP_LOST, target, amount=result["amount"])
        elif eid == "instant_hp_loss":
            if result["amount"] > 0:
                self._emit(GameEvent.HP_LOST, target, amount=result["amount"])
        elif eid == "instant_block":
            if result["amount"] > 0:
                self._emit(GameEvent.BLOCK_GAINED, target, amount=result["amount"])
        elif eid == "instant_exhaust":
            for card_id in result["card_ids"]:
                self._emit(GameEvent.CARD_EXHAUSTED, target, card=create_card(card_id))
        elif eid in ("instant_draw", "instant_draw_until"):
            if result["amount"] > 0:
                self._emit(GameEvent.CARD_DRAWN, target,
                           amount=result["amount"], card_ids=result["card_ids"])
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
            # Deduped: Gang Up pays per attacker, not per hit.
            attacker = payload.get("attacker")
            seen = subject.turn_counters.setdefault("attacked_by", [])
            if attacker is not None and attacker not in seen:
                seen.append(attacker)

        if event is GameEvent.CARD_EXHAUSTED:
            # By anyone, for Midnight.
            self.combat_counters["cards_exhausted"] = (
                self.combat_counters.get("cards_exhausted", 0) + 1)

        if event is GameEvent.CARD_PLAYED and subject is not None:
            # Juggling and Stomp count Attacks, not cards.
            played = payload.get("card")
            if played is not None and played.card_type is CardType.ATTACK:
                subject.turn_counters["attacks_played"] = (
                    subject.turn_count("attacks_played") + 1)

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
        elif event in self.HAND_EVENTS:
            for ally in self.allies:
                if not ally.is_alive():
                    continue
                for card_id in list(ally.hand):
                    card = create_card(card_id)
                    out = card.on_event(
                        event, self._context_for(ally, subject, payload))
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
            return self._validated_target(card, target, self.allies, "ally")

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
    def _free_bucket(ally, card_id):
        """The tally holding a free play of this card, or None if it costs.

        This-turn is checked first so a card granted free by both keeps the
        longer-lived combat grant for later."""
        for bucket in (ally.free_this_turn, ally.free_this_combat):
            if card_id in bucket:
                return bucket
        return None

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
        return self.rng.choice(living)

    def _run_enemy_turn(self):
        fallback_target = self._first_alive_ally()
        for enemy in self.enemies:
            if not enemy.is_alive():
                continue
            stun = enemy.get_status("stun")
            if stun is not None and stun.amount > 0:
                # The whole turn goes, block clearing included. Counted down
                # here so a stun applied mid-turn is not spent before it lands.
                stun.amount -= 1
                continue
            enemy.clear_block()
            context = self._context_for(enemy, target=fallback_target)
            for effect in enemy.get_effects(context):
                self._intercept(effect)
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
            if covering is not None and covering.amount > 0:
                effect.target = ally
                return

    def _first_alive_ally(self):
        for ally in self.allies:
            if ally.is_alive():
                return ally
        return None

    def _tick_statuses(self, units):
        for unit in units:
            if not unit.is_alive():
                continue
            for status in list(unit.statuses.values()):
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
        self.rng.shuffle(ally.draw_pile)
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
        drawn = ally.draw(count, self.rng)
        self._drain_shuffles(ally)
        # The opening hand and every turn's hand are draws too, and are
        # where most draws happen.
        if drawn:
            self._emit(GameEvent.CARD_DRAWN, ally, amount=len(drawn),
                       card_ids=drawn)
        return drawn

    def _check_combat_end(self):
        if not any(enemy.is_alive() for enemy in self.enemies):
            self.phase = CombatPhase.OVER
            self.result = CombatResult.VICTORY
            return True
        if not any(ally.is_alive() for ally in self.allies):
            self.phase = CombatPhase.OVER
            self.result = CombatResult.DEFEAT
            return True
        return False
