from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.pyre import Pyre as PyreStatus


class Pyre(Card):
    AMOUNT = 1

    def __init__(self):
        super().__init__(
            card_id = "pyre",
            name = "Pyre",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 2,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [
            PyreStatus(
                source=context.source, target=context.source, amount=self.AMOUNT),
        ]
