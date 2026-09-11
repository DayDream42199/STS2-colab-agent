from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.stampede import Stampede as StampedeStatus


class Stampede(Card):
    def __init__(self):
        super().__init__(
            card_id = "stampede",
            name = "Stampede",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 2,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [StampedeStatus(
            source=context.source, target=context.source, amount=1)]
