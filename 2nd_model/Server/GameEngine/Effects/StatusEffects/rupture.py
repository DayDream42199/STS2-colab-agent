from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from .strength import Strength


class Rupture(StatusEffect):
    """Whenever you lose HP on your turn, gain Strength."""

    def __init__(self, source, target, amount):
        super().__init__("rupture")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat

    def on_event(self, event, context):
        if event is not GameEvent.HP_LOST:
            return None
        if context.target is not context.source:
            return None
        if context.payload.get("phase") != "PLAYER_TURN":
            return None
        return [Strength(
            source=context.source, target=context.source, amount=self.amount)]
