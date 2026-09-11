from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.corruption import Corruption as CorruptionStatus


class Corruption(Card):
    def __init__(self):
        super().__init__(
            card_id = "corruption",
            name = "Corruption",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.ANCIENT,
            cost = 3,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [CorruptionStatus(
            source=context.source, target=context.source, amount=1)]
