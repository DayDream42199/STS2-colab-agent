from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_block import InstantBlock
from ..InstantEffects.instant_hp_loss import InstantHpLoss


class CrimsonMantle(StatusEffect):
    """At the start of your turn, lose 1 HP and gain Block."""

    def __init__(self, source, target, amount):
        super().__init__("crimson_mantle")
        self.source = source
        self.target = target
        self.amount = amount

    HP_LOSS = 1

    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat

    def on_event(self, event, context):
        if event is not GameEvent.TURN_START:
            return None
        if context.target is not context.source:
            return None
        return [
            InstantHpLoss(
                source=context.source, target=context.source, amount=self.HP_LOSS),
            InstantBlock(
                source=context.source, target=context.source, amount=self.amount),
        ]
