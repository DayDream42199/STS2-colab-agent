from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.rupture import Rupture as RuptureStatus


class Rupture(Card):
    AMOUNT = 1

    def __init__(self):
        super().__init__(
            card_id = "rupture",
            name = "Rupture",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [
            RuptureStatus(
                source=context.source, target=context.source, amount=self.AMOUNT),
        ]
