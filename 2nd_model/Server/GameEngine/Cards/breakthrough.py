from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_hp_loss import InstantHpLoss

class Breakthrough(Card):
    HP_LOSS = 1
    DAMAGE = 9

    def __init__(self):
        super().__init__(
            card_id = "breakthrough",
            name = "Breakthrough",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.ALL_ENEMIES
        )

    def get_effects(self, context):
        effects = [InstantHpLoss(
            source=context.source, target=context.source, amount=self.HP_LOSS)]
        for enemy in context.all_enemies:
            if enemy.is_alive():
                effects.append(InstantDamage(
                    source=context.source, target=enemy, amount=self.DAMAGE))
        return effects
