from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_energy import InstantEnergy


class DelayedEnergy(StatusEffect):
    """Grant Energy at the start of each of the next `amount` turns."""

    ENERGY = 2

    def __init__(self, source, target, amount):
        super().__init__("delayed_energy")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass

    def on_event(self, event, context):
        if event is not GameEvent.TURN_START:
            return None
        if context.target is not context.source or self.amount <= 0:
            return None
        self.amount -= 1
        return [InstantEnergy(
            source=context.source, target=context.source, amount=self.ENERGY)]
