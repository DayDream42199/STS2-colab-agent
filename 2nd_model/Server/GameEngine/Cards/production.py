from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_energy import InstantEnergy


class Production(Card):
    ENERGY = 2

    def __init__(self):
        super().__init__(
            card_id = "production",
            name = "Production",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        return [InstantEnergy(
            source=context.source, target=context.source, amount=self.ENERGY)]
