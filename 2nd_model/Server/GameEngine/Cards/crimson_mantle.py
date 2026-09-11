from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.crimson_mantle import CrimsonMantle as CrimsonMantleStatus


class CrimsonMantle(Card):
    AMOUNT = 7

    def __init__(self):
        super().__init__(
            card_id = "crimson_mantle",
            name = "Crimson Mantle",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [
            CrimsonMantleStatus(
                source=context.source, target=context.source, amount=self.AMOUNT),
        ]
