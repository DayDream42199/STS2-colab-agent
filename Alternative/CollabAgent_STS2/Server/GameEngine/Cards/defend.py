from ._card import Card
from ._card_enums import CardType, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock

class Defend(Card):
    def __init__(self):
        super().__init__(
            card_id = "defend",
            name = "Defend",
            card_type = CardType.SKILL,
            rarity = CardRarity.BASIC,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [
            InstantBlock(
                source=context.source,
                target=context.target,
                amount=5
            )
        ]