from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.plating import Plating


class StoneArmor(Card):
    PLATING = 4

    def __init__(self):
        super().__init__(
            card_id = "stone_armor",
            name = "Stone Armor",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [Plating(
            source=context.source, target=context.source, amount=self.PLATING)]
