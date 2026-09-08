from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.dark_embrace import DarkEmbrace as DarkEmbraceStatus


class DarkEmbrace(Card):
    AMOUNT = 1

    def __init__(self):
        super().__init__(
            card_id = "dark_embrace",
            name = "Dark Embrace",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 2,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [
            DarkEmbraceStatus(
                source=context.source, target=context.source, amount=self.AMOUNT),
        ]
