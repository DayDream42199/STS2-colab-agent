from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock


class Lift(Card):
    BLOCK = 11

    def __init__(self):
        super().__init__(
            card_id = "lift",
            name = "Lift",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ALLY
        )

    def get_effects(self, context):
        return [InstantBlock(
            source=context.source, target=context.target, amount=self.BLOCK)]
