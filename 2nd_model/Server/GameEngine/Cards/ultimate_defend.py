from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock


class UltimateDefend(Card):
    BLOCK = 11

    def __init__(self):
        super().__init__(
            card_id = "ultimate_defend",
            name = "Ultimate Defend",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [InstantBlock(
            source=context.source, target=context.source, amount=self.BLOCK)]
