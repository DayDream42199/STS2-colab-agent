from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_block import InstantBlock
from ...Cards._card_enums import CardType


class Rage(StatusEffect):
    """Whenever you play an Attack this turn, gain Block."""

    def __init__(self, source, target, amount):
        super().__init__("rage")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        self.amount = 0  # lasts only the turn it was played

    def on_event(self, event, context):
        if event is not GameEvent.CARD_PLAYED:
            return None
        if context.target is not context.source:
            return None
        card = context.payload.get("card")
        if card is None or card.card_type is not CardType.ATTACK:
            return None
        return [InstantBlock(
            source=context.source, target=context.source, amount=self.amount)]
