from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.hellraiser import Hellraiser as HellraiserStatus


class Hellraiser(Card):
    def __init__(self):
        super().__init__(
            card_id = "hellraiser",
            name = "Hellraiser",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 2,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [HellraiserStatus(
            source=context.source, target=context.source, amount=1)]
