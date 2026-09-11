from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_hp_loss import InstantHpLoss
from ..Effects.InstantEffects.instant_energy import InstantEnergy

class Bloodletting(Card):
    HP_LOSS = 3
    ENERGY = 2

    def __init__(self):
        super().__init__(
            card_id = "bloodletting",
            name = "Bloodletting",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [
            InstantHpLoss(
                source=context.source, target=context.source, amount=self.HP_LOSS),
            InstantEnergy(
                source=context.source, target=context.source, amount=self.ENERGY),
        ]
