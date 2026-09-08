from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.strength import Strength

class Inflame(Card):
    STRENGTH = 2

    def __init__(self):
        super().__init__(
            card_id = "inflame",
            name = "Inflame",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [Strength(
            source=context.source, target=context.source, amount=self.STRENGTH)]
