from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties


class SporeMind(Card):
    def __init__(self):
        super().__init__(
            card_id = "spore_mind",
            name = "Spore Mind",
            card_type = CardType.CURSE,
            card_class = CardClass.CURSE,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        return []
