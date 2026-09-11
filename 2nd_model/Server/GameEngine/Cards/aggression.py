from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.aggression import Aggression as AggressionStatus


class Aggression(Card):
    def __init__(self):
        super().__init__(
            card_id = "aggression",
            name = "Aggression",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [AggressionStatus(
            source=context.source, target=context.source, amount=1)]
