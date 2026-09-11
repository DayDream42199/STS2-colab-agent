from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_draw import InstantDraw


class Vicious(StatusEffect):
    """Whenever you apply Vulnerable, draw a card."""

    def __init__(self, source, target, amount):
        super().__init__("vicious")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat

    def on_event(self, event, context):
        if event is not GameEvent.STATUS_APPLIED:
            return None
        # Fires on what WE applied, so the subject is the victim, not us.
        if context.payload.get("applied_by") is not context.source:
            return None
        if context.payload.get("effect_id") != "vulnerable":
            return None
        return [InstantDraw(source=context.source, target=context.source,
                           amount=self.amount, rng=context.rng)]
