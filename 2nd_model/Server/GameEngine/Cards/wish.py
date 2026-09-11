from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_move_card import InstantMoveCard


class Wish(Card):
    def __init__(self):
        super().__init__(
            card_id = "wish",
            name = "Wish",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.ANCIENT,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        ally = context.source
        if not ally.draw_pile:
            return []

        def take(chosen):
            return [InstantMoveCard(
                source=ally, target=ally, card_ids=[chosen],
                from_pile=InstantMoveCard.DRAW,
                to_pile=InstantMoveCard.HAND)]

        context.ask(ally, "Put a card from your Draw Pile into your Hand",
                    lambda: list(ally.draw_pile), take)
        return []
