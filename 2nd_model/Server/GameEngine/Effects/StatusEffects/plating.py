from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_block import InstantBlock


class Plating(StatusEffect):
    """At the end of your turn, gain Block equal to your Plating, then lose 1.

    End of turn, not start: the Block has to survive into the enemy phase."""

    def __init__(self, source, target, amount):
        super().__init__("plating")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # paid out and counted down together, in on_event

    def on_event(self, event, context):
        if event is not GameEvent.TURN_END:
            return None
        if context.target is not context.source or self.amount <= 0:
            return None
        block = self.amount
        self.amount -= 1
        return [InstantBlock(
            source=context.source, target=context.source, amount=block)]
