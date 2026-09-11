from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.mayhem import Mayhem as MayhemStatus


class Mayhem(Card):
    def __init__(self):
        super().__init__(
            card_id = "mayhem",
            name = "Mayhem",
            card_type = CardType.POWER,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 2,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [MayhemStatus(
            source=context.source, target=context.source, amount=1)]
