from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties


class Normality(Card):
    PLAY_CAP = 3

    def __init__(self):
        super().__init__(
            card_id = "normality",
            name = "Normality",
            card_type = CardType.CURSE,
            card_class = CardClass.CURSE,
            rarity = CardRarity.COMMON,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(playable=False)
        )

    def get_effects(self, context):
        return []
