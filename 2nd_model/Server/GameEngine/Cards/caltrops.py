from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.caltrops import Caltrops as CaltropsStatus


class Caltrops(Card):
    THORNS = 3

    def __init__(self):
        super().__init__(
            card_id = "caltrops",
            name = "Caltrops",
            card_type = CardType.POWER,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [CaltropsStatus(
            source=context.source, target=context.source, amount=self.THORNS)]
