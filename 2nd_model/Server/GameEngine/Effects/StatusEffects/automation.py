from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_energy import InstantEnergy


class Automation(StatusEffect):
    """Every Nth card drawn, gain Energy. Counts across the whole combat."""

    EVERY = 10
    ENERGY = 1

    def __init__(self, source, target, amount):
        super().__init__("automation")
        self.source = source
        self.target = target
        self.amount = amount
        self.drawn = 0

    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat

    def on_event(self, event, context):
        if event is not GameEvent.CARD_DRAWN:
            return None
        if context.target is not context.source:
            return None
        self.drawn += context.payload.get("amount", 1)
        if self.drawn < self.EVERY:
            return None
        self.drawn -= self.EVERY
        return [InstantEnergy(
            source=context.source, target=context.source, amount=self.ENERGY)]
