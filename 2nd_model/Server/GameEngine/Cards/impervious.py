from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_block import InstantBlock


class Impervious(Card):
    BLOCK = 30

    def __init__(self):
        super().__init__(
            card_id = "impervious",
            name = "Impervious",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 2,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        return [InstantBlock(
            source=context.source, target=context.source, amount=self.BLOCK)]
