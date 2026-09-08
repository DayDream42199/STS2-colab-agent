from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.inferno import Inferno as InfernoStatus


class Inferno(Card):
    AMOUNT = 6

    def __init__(self):
        super().__init__(
            card_id = "inferno",
            name = "Inferno",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 2,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [
            InfernoStatus(
                source=context.source, target=context.source, amount=self.AMOUNT),
        ]
