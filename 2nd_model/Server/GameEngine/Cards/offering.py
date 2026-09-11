from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_hp_loss import InstantHpLoss
from ..Effects.InstantEffects.instant_energy import InstantEnergy
from ..Effects.InstantEffects.instant_draw import InstantDraw


class Offering(Card):
    HP_LOSS = 6
    ENERGY = 2
    CARDS = 3

    def __init__(self):
        super().__init__(
            card_id = "offering",
            name = "Offering",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        return [
            InstantHpLoss(
                source=context.source, target=context.source, amount=self.HP_LOSS),
            InstantEnergy(
                source=context.source, target=context.source, amount=self.ENERGY),
            InstantDraw(source=context.source, target=context.source,
                        amount=self.CARDS, rng=context.rng),
        ]
