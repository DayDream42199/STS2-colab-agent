from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.prep_time import PrepTime as PrepTimeStatus


class PrepTime(Card):
    VIGOR = 4

    def __init__(self):
        super().__init__(
            card_id = "prep_time",
            name = "Prep Time",
            card_type = CardType.POWER,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [PrepTimeStatus(
            source=context.source, target=context.source, amount=self.VIGOR)]
