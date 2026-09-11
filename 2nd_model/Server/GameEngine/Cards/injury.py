from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties


class Injury(Card):
    def __init__(self):
        super().__init__(
            card_id = "injury",
            name = "Injury",
            card_type = CardType.CURSE,
            card_class = CardClass.CURSE,
            rarity = CardRarity.COMMON,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(playable=False)
        )

    def get_effects(self, context):
        return []
