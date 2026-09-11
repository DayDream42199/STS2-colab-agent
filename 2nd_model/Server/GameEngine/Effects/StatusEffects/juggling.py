from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_add_card import InstantAddCard


class Juggling(StatusEffect):
    """Add a copy of the third Attack you play each turn into your Hand."""

    NTH = 3

    def __init__(self, source, target, amount):
        super().__init__("juggling")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass

    def on_event(self, event, context):
        from ...Cards._card_enums import CardType

        if event is not GameEvent.CARD_PLAYED:
            return None
        if context.target is not context.source:
            return None
        card = context.payload.get("card")
        if card is None or card.card_type is not CardType.ATTACK:
            return None
        if context.source.turn_count("attacks_played") != self.NTH:
            return None
        return [InstantAddCard(
            source=context.source, target=context.source,
            card_id=card.card_id, pile=InstantAddCard.HAND)]
