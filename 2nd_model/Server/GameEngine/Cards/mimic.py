from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_block import InstantBlock


class Mimic(Card):
    def __init__(self):
        super().__init__(
            card_id = "mimic",
            name = "Mimic",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ALLY,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        # Block is read off the ally at play time, so it mirrors whatever they
        # are holding right now rather than a fixed number.
        return [InstantBlock(
            source=context.source,
            target=context.source,
            amount=context.target.block,
        )]
