from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock


class Entrench(Card):
    def __init__(self):
        super().__init__(
            card_id = "entrench",
            name = "Entrench",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 2,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        # Read live: doubling means granting again whatever we already hold.
        return [InstantBlock(
            source=context.source,
            target=context.source,
            amount=context.source.block,
        )]
