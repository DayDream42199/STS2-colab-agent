import random
from enum import Enum

from ..Context.context import Context
from ..Events.game_event import GameEvent
from ..Resolution.resolver import Resolver
from ..Registry.card_registry import create_card
from ..Cards._card_enums import CardType, TargetType


class CombatPhase(Enum):
    NOT_STARTED = "NOT_STARTED"
    PLAYER_TURN = "PLAYER_TURN"
    ENEMY_TURN = "ENEMY_TURN"
    OVER = "OVER"


class CombatResult(Enum):
    VICTORY = "VICTORY"
    DEFEAT = "DEFEAT"


class Combat:
    """Satisfies the surface documented in COMBAT_INTERFACE.md. Session
    drives everything through this class and never reaches into Context,
    Resolution, or Registry directly."""

    HAND_SIZE = 5

    # A reaction can cause another reaction (block -> Juggernaut damage ->
    # Flame Barrier). Bounded so two powers cannot ping-pong forever.
    MAX_EVENT_DEPTH = 3

    def __init__(self, allies, enemies, rng=None):
        self.allies = list(allies)
        self.enemies = list(enemies)
        self.rng = rng if rng is not None else random.Random()

        self.phase = CombatPhase.NOT_STARTED
        self.result = None
        self._event_depth = 0

    # --- lifecycle -------------------------------------------------------

    def start(self):
        for ally in self.allies:
            self._build_draw_pile(ally)
            self._draw_cards(ally, self.HAND_SIZE)

        for enemy in self.enemies:
            enemy.choose_intent(self._context_for(enemy))

        self.phase = CombatPhase.PLAYER_TURN
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
        if not (0 <= hand_index < len(ally.hand)):
            raise IndexError(f"hand_index {hand_index} out of range.")

        card_id = ally.hand[hand_index]
        card = create_card(card_id)

        if ally.energy < card.cost:
            raise ValueError(f"Not enough energy to play {card.name}.")

        resolved_target = self._resolve_target(card, ally, target)

        # Pay the cost and leave the hand BEFORE resolving. If an effect
        # raises midway, the effects already applied stand, but the card
        # must not still be sitting in hand replayable for free.
        ally.spend_energy(card.cost)
        ally.hand.pop(hand_index)
        # Powers leave play once applied: they go to neither the discard
        # pile nor the exhaust pile, so they cannot be drawn again.
        if not card.properties.exhaust and card.card_type is not CardType.POWER:
            ally.discard_pile.append(card_id)

        context = self._context_for(ally, resolved_target)
        # Resolver returns None for a no-op (e.g. a status aimed at a unit
        # that died earlier in this same card); keep those out of the wire.
        results = [
            result
            for result in (self._resolve(e) for e in card.get_effects(context))
            if result is not None
        ]

        self._emit(GameEvent.CARD_PLAYED, ally, card=card)
        if card.properties.exhaust:
            self._emit(GameEvent.CARD_EXHAUSTED, ally, card=card)

        self._check_combat_end()
        return results

    def end_player_turn(self):
        if self.phase != CombatPhase.PLAYER_TURN:
            raise RuntimeError("It is not the player turn.")

        for ally in self.allies:
            if ally.is_alive():
                self._emit(GameEvent.TURN_END, ally)

        self._tick_statuses(self.allies)
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
        for ally in self.allies:
            if ally.is_alive():
                ally.start_turn()
                self._draw_cards(ally, self.HAND_SIZE)
                # Emitted after the reset, so a power granting Block at turn
                # start is not wiped by the same turn's block clear.
                self._emit(GameEvent.TURN_START, ally)

    # --- serialization -------------------------------------------------------

    def to_dict(self):
        return {
            "phase": self.phase.name,
            "result": self.result.name if self.result is not None else None,
            "allies": [ally.to_dict() for ally in self.allies],
            "enemies": [enemy.to_dict() for enemy in self.enemies],
        }

    # --- internals -------------------------------------------------------

    def _context_for(self, source, target=None, payload=None):
        return Context(
            source=source,
            target=target,
            all_allies=self.allies,
            all_enemies=self.enemies,
            rng=self.rng,
            payload=payload,
        )

    # --- events -----------------------------------------------------------

    def _resolve(self, effect):
        """Resolve one effect and emit whatever it caused."""
        result = Resolver.resolve(effect)
        if result is not None:
            self._emit_for(effect, result)
        return result

    def _emit_for(self, effect, result):
        """Turn a resolver result into the events it represents."""
        eid = result["effect_id"]
        target = effect.target

        if eid == "instant_damage":
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
        elif eid == "instant_draw":
            if result["amount"] > 0:
                self._emit(GameEvent.CARD_DRAWN, target, amount=result["amount"])
        elif eid not in ("instant_energy",):
            # Everything else is a status landing on someone.
            self._emit(GameEvent.STATUS_APPLIED, target,
                       effect_id=eid, applied_by=effect.source)

    def _emit(self, event, subject=None, **payload):
        """Offer an event to every living unit's statuses and resolve whatever
        they return. Depth-bounded: a reaction may cause a reaction, but not
        without limit."""
        if self._event_depth >= self.MAX_EVENT_DEPTH:
            return []

        payload["phase"] = self.phase.name
        produced = []
        for unit in self.allies + self.enemies:
            if not unit.is_alive():
                continue
            for status in list(unit.statuses.values()):
                out = status.on_event(event, self._context_for(unit, subject, payload))
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

        # No single target: the card fans out over context.all_enemies /
        # context.all_allies itself, the way Dummy1.get_effects does.
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
        return self.rng.choice(living)

    def _run_enemy_turn(self):
        # STS2 co-op enemies attack the whole party by default, so "attack"
        # style intents should loop over context.all_allies themselves (see
        # Dummy1.get_effects). context.target here is only a fallback for
        # enemy moves that genuinely single out one player (e.g. a future
        # elite "focus" mechanic) and should not be used for normal attacks.
        fallback_target = self._first_alive_ally()
        for enemy in self.enemies:
            if not enemy.is_alive():
                continue
            # Block clears at the start of the enemy's own turn, same rule
            # as allies (Ally.start_turn() does the equivalent). Without
            # this, block from a prior "block" intent would persist forever
            # instead of expiring before the enemy's next action.
            enemy.clear_block()
            context = self._context_for(enemy, target=fallback_target)
            for effect in enemy.get_effects(context):
                self._resolve(effect)
            if self._check_combat_end():
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
        # Dead allies discard too. They can no longer act, so leaving cards
        # in their hand only makes the client render a hand for a corpse.
        for ally in self.allies:
            kept = []
            for card_id in ally.hand:
                if create_card(card_id).properties.retain:
                    kept.append(card_id)
                else:
                    ally.discard_pile.append(card_id)
            ally.hand = kept

    def _build_draw_pile(self, ally):
        ally.draw_pile = list(ally.deck)
        self.rng.shuffle(ally.draw_pile)

    def _draw_cards(self, ally, count):
        # Pile logic lives on Ally so the InstantDraw effect can reuse it.
        ally.draw(count, self.rng)

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
