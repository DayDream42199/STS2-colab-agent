from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.vicious import Vicious as ViciousStatus


class Vicious(Card):
    AMOUNT = 1

    def __init__(self):
        super().__init__(
            card_id = "vicious",
            name = "Vicious",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [
            ViciousStatus(
                source=context.source, target=context.source, amount=self.AMOUNT),
        ]
