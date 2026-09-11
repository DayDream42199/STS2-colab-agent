from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from .vigor import Vigor


class PrepTime(StatusEffect):
    """At the start of your turn, gain Vigor. `amount` is the Vigor, not a
    duration - the power lasts the whole combat."""

    def __init__(self, source, target, amount):
        super().__init__("prep_time")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass

    def on_event(self, event, context):
        if event is not GameEvent.TURN_START:
            return None
        if context.target is not context.source:
            return None
        return [Vigor(
            source=context.source, target=context.source, amount=self.amount)]
