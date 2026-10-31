from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_energy import InstantEnergy


class DelayedEnergy(StatusEffect):
    """Gain `amount` Energy at the start of your next turn - the game's
    EnergyNextTurnPower. Two of them add up into one bigger payout."""

    def __init__(self, source, target, amount):
        super().__init__("delayed_energy")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # amount is Energy, not a duration

    def on_event(self, event, context):
        if event is not GameEvent.TURN_START:
            return None
        if context.target is not context.source or self.amount <= 0:
            return None
        energy, self.amount = self.amount, 0   # spent; the next tick removes it
        return [InstantEnergy(
            source=context.source, target=context.source, amount=energy)]
