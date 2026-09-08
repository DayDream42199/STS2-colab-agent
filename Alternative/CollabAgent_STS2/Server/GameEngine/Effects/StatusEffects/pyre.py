from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_energy import InstantEnergy


class Pyre(StatusEffect):
    """Gain Energy at the start of each turn."""

    def __init__(self, source, target, amount):
        super().__init__("pyre")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat

    def on_event(self, event, context):
        if event is not GameEvent.TURN_START:
            return None
        if context.target is not context.source:
            return None
        return [InstantEnergy(
            source=context.source, target=context.source, amount=self.amount)]
