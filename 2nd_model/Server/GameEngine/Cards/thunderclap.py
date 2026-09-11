from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.StatusEffects.vulnerable import Vulnerable

class Thunderclap(Card):
    DAMAGE = 4
    VULNERABLE = 1

    def __init__(self):
        super().__init__(
            card_id = "thunderclap",
            name = "Thunderclap",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.ALL_ENEMIES
        )

    def get_effects(self, context):
        effects = []
        for enemy in context.all_enemies:
            if not enemy.is_alive():
                continue
            effects.append(InstantDamage(
                source=context.source, target=enemy, amount=self.DAMAGE))
            effects.append(Vulnerable(
                source=context.source, target=enemy, amount=self.VULNERABLE))
        return effects
