from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_energy import InstantEnergy


class ForgottenRitual(Card):
    ENERGY = 3

    def __init__(self):
        super().__init__(
            card_id = "forgotten_ritual",
            name = "Forgotten Ritual",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        return [InstantEnergy(
            source=context.source, target=context.source, amount=self.ENERGY)]
