from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_draw import InstantDraw


class MasterOfStrategy(Card):
    CARDS = 3

    def __init__(self):
        super().__init__(
            card_id = "master_of_strategy",
            name = "Master of Strategy",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        return [InstantDraw(source=context.source, target=context.source,
                            amount=self.CARDS, rng=context.rng)]
