from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.rolling_boulder import RollingBoulder as RollingBoulderStatus


class RollingBoulder(Card):
    DAMAGE = 5

    def __init__(self):
        super().__init__(
            card_id = "rolling_boulder",
            name = "Rolling Boulder",
            card_type = CardType.POWER,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 3,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [RollingBoulderStatus(
            source=context.source, target=context.source, amount=self.DAMAGE)]
