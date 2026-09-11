from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties


class MindRot(Card):
    DRAW_PENALTY = 1

    def __init__(self):
        super().__init__(
            card_id = "mind_rot",
            name = "Mind Rot",
            card_type = CardType.STATUS,
            card_class = CardClass.STATUS,
            rarity = CardRarity.COMMON,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(playable=False)
        )

    def get_effects(self, context):
        return []
