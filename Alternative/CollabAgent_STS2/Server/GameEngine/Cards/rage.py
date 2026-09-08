from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.rage import Rage as RageStatus


class Rage(Card):
    AMOUNT = 3

    def __init__(self):
        super().__init__(
            card_id = "rage",
            name = "Rage",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [
            RageStatus(
                source=context.source, target=context.source, amount=self.AMOUNT),
        ]
