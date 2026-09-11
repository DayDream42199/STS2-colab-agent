from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.unmovable import Unmovable as UnmovableStatus


class Unmovable(Card):
    def __init__(self):
        super().__init__(
            card_id = "unmovable",
            name = "Unmovable",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 2,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [UnmovableStatus(
            source=context.source, target=context.source, amount=1)]
