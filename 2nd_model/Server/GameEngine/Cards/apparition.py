from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.StatusEffects.intangible import Intangible


class Apparition(Card):
    INTANGIBLE = 1

    def __init__(self):
        super().__init__(
            card_id = "apparition",
            name = "Apparition",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.ANCIENT,
            cost = 1,
            target_type = TargetType.SELF,
            properties = CardProperties(ethereal=True, exhaust=True)
        )

    def get_effects(self, context):
        return [Intangible(
            source=context.source, target=context.source, amount=self.INTANGIBLE)]
