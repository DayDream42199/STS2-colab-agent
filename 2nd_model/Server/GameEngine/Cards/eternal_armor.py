from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.plating import Plating


class EternalArmor(Card):
    PLATING = 9

    def __init__(self):
        super().__init__(
            card_id = "eternal_armor",
            name = "Eternal Armor",
            card_type = CardType.POWER,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 3,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [Plating(
            source=context.source, target=context.source, amount=self.PLATING)]
