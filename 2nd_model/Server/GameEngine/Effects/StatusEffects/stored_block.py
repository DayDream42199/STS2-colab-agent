from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_block import InstantBlock


class StoredBlock(StatusEffect):
    """Gain `amount` Block at the start of your next turn.

    `amount` is a snapshotted Block total, not a duration - it must not tick."""

    def __init__(self, source, target, amount):
        super().__init__("stored_block")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # amount is Block, not a duration

    def on_event(self, event, context):
        if event is not GameEvent.TURN_START:
            return None
        if context.target is not context.source or self.amount <= 0:
            return None
        block = self.amount
        self.amount = 0  # spent; the next tick removes it
        return [InstantBlock(
            source=context.source, target=context.source, amount=block)]
