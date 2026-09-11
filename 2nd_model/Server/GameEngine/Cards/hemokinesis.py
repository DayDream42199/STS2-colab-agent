from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_hp_loss import InstantHpLoss

class Hemokinesis(Card):
    HP_LOSS = 2
    DAMAGE = 15

    def __init__(self):
        super().__init__(
            card_id = "hemokinesis",
            name = "Hemokinesis",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        return [
            InstantHpLoss(
                source=context.source, target=context.source, amount=self.HP_LOSS),
            InstantDamage(
                source=context.source, target=context.target, amount=self.DAMAGE),
        ]
