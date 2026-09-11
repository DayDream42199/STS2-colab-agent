from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.StatusEffects.vulnerable import Vulnerable


class Tremble(Card):
    VULNERABLE = 3

    def __init__(self):
        super().__init__(
            card_id = "tremble",
            name = "Tremble",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.ENEMY,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        return [Vulnerable(
            source=context.source, target=context.target, amount=self.VULNERABLE)]
