from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties


class Debris(Card):
    def __init__(self):
        super().__init__(
            card_id = "debris",
            name = "Debris",
            card_type = CardType.STATUS,
            card_class = CardClass.STATUS,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        # Its whole purpose is to be spent clearing itself out of the deck.
        return []
