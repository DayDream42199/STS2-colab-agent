from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_damage import InstantDamage


class FlameBarrier(StatusEffect):
    """Whenever you are attacked, deal damage back. Lasts until the start of
    your next turn.

    It deliberately does NOT expire in the end-of-turn tick: ally statuses are
    ticked before the enemy phase runs, so a barrier that decayed there would
    be gone by the time anything attacked. Instead it clears itself on the
    owner's next TURN_START, which is what "this turn" means for a defensive
    effect."""

    def __init__(self, source, target, amount):
        super().__init__("flame_barrier")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # survives into the enemy phase; see the class docstring

    def on_event(self, event, context):
        if context.target is not context.source:
            return None

        if event is GameEvent.TURN_START:
            self.amount = 0  # spent; the next tick removes it
            return None

        if event is not GameEvent.ATTACKED or self.amount <= 0:
            return None
        attacker = context.payload.get("attacker")
        if attacker is None or not attacker.is_alive():
            return None
        return [InstantDamage(
            source=context.source, target=attacker, amount=self.amount)]
