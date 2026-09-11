from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_draw import InstantDraw


class DelayedDraw(StatusEffect):
    """Draw cards at the start of each of the next `amount` turns."""

    CARDS = 2

    def __init__(self, source, target, amount):
        super().__init__("delayed_draw")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # counted down on use, not on the turn tick

    def on_event(self, event, context):
        if event is not GameEvent.TURN_START:
            return None
        if context.target is not context.source or self.amount <= 0:
            return None
        self.amount -= 1
        return [InstantDraw(source=context.source, target=context.source,
                            amount=self.CARDS, rng=context.rng)]
