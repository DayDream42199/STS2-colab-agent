from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties


class Dazed(Card):
    def __init__(self):
        super().__init__(
            card_id = "dazed",
            name = "Dazed",
            card_type = CardType.STATUS,
            card_class = CardClass.STATUS,
            rarity = CardRarity.COMMON,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(playable=False, ethereal=True)
        )

    def get_effects(self, context):
        return []
