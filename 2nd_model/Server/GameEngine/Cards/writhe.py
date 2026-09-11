from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties


class Writhe(Card):
    def __init__(self):
        super().__init__(
            card_id = "writhe",
            name = "Writhe",
            card_type = CardType.CURSE,
            card_class = CardClass.CURSE,
            rarity = CardRarity.COMMON,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(playable=False, innate=True)
        )

    def get_effects(self, context):
        return []
