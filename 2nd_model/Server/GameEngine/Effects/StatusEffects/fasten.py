from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_block import InstantBlock


class Fasten(StatusEffect):
    """Defend cards grant `amount` extra Block.

    On CARD_PLAYED, because modify_block_gained cannot see which card."""

    def __init__(self, source, target, amount):
        super().__init__("fasten")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass

    def on_event(self, event, context):
        if event is not GameEvent.CARD_PLAYED:
            return None
        if context.target is not context.source:
            return None
        card = context.payload.get("card")
        if card is None or card.card_id != "defend":
            return None
        return [InstantBlock(
            source=context.source, target=context.source, amount=self.amount)]
