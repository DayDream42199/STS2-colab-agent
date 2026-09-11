from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.calamity import Calamity as CalamityStatus


class Calamity(Card):
    def __init__(self):
        super().__init__(
            card_id = "calamity",
            name = "Calamity",
            card_type = CardType.POWER,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 3,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [CalamityStatus(
            source=context.source, target=context.source, amount=1)]
