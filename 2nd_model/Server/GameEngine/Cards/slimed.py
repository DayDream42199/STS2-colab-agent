from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_draw import InstantDraw


class Slimed(Card):
    CARDS = 1

    def __init__(self):
        super().__init__(
            card_id = "slimed",
            name = "Slimed",
            card_type = CardType.STATUS,
            card_class = CardClass.STATUS,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        return [InstantDraw(source=context.source, target=context.source,
                            amount=self.CARDS, rng=context.rng)]
