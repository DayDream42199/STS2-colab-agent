from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.cruelty import Cruelty as CrueltyStatus


class Cruelty(Card):
    # Percent added to Vulnerable's 1.5x for your attacks: 1.75x, 2x upgraded.
    AMOUNT = 25

    def __init__(self):
        super().__init__(
            card_id = "cruelty",
            name = "Cruelty",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [CrueltyStatus(
            source=context.source, target=context.source, amount=self.AMOUNT)]
