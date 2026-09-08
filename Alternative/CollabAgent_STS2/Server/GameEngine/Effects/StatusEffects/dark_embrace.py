from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_draw import InstantDraw


class DarkEmbrace(StatusEffect):
    """Whenever a card is Exhausted, draw a card."""

    def __init__(self, source, target, amount):
        super().__init__("dark_embrace")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat

    def on_event(self, event, context):
        if event is not GameEvent.CARD_EXHAUSTED:
            return None
        if context.target is not context.source:
            return None
        return [InstantDraw(source=context.source, target=context.source,
                           amount=self.amount, rng=context.rng)]
