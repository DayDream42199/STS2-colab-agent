from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.barricade import Barricade as BarricadeStatus


class Barricade(Card):
    def __init__(self):
        super().__init__(
            card_id = "barricade",
            name = "Barricade",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 3,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [BarricadeStatus(
            source=context.source, target=context.source, amount=1)]
