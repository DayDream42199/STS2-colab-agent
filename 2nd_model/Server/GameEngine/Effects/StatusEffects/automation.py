from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_energy import InstantEnergy


class Automation(StatusEffect):
    """Every 10th card drawn, gain `amount` Energy. Counts across the whole
    combat. Each Automation played counts its own draws from when it was
    played, as the game's AutomationPower instances do: `counts` holds
    [energy, cards drawn] per copy."""

    EVERY = 10

    def __init__(self, source, target, amount):
        super().__init__("automation")
        self.source = source
        self.target = target
        self.amount = amount
        self.counts = [[amount, 0]]

    def absorb(self, other):
        self.counts.extend(other.counts)
        self.amount = sum(energy for energy, _ in self.counts)

    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat

    def on_event(self, event, context):
        if event is not GameEvent.CARD_DRAWN:
            return None
        if context.target is not context.source:
            return None
        energy = 0
        for count in self.counts:
            count[1] += context.payload.get("amount", 1)
            while count[1] >= self.EVERY:
                count[1] -= self.EVERY
                energy += count[0]
        if not energy:
            return None
        return [InstantEnergy(
            source=context.source, target=context.source, amount=energy)]
