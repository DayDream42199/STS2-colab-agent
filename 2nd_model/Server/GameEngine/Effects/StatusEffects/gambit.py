from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_hp_loss import InstantHpLoss


class Gambit(StatusEffect):
    """If the owner takes unblocked attack damage, they die.

    ATTACKED carries what got through Block, so a blocked hit reports 0."""

    def __init__(self, source, target, amount):
        super().__init__("gambit")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass

    def on_event(self, event, context):
        if event is not GameEvent.ATTACKED:
            return None
        if context.target is not context.source:
            return None
        if context.payload.get("amount", 0) <= 0:
            return None
        return [InstantHpLoss(source=context.source, target=context.source,
                              amount=context.source.current_hp)]
