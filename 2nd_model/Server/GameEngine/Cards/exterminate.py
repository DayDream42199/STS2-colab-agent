from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class Exterminate(Card):
    DAMAGE = 3
    ROUNDS = 4

    def __init__(self):
        super().__init__(
            card_id = "exterminate",
            name = "Exterminate",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ALL_ENEMIES
        )

    def get_effects(self, context):
        effects = []
        for _ in range(self.ROUNDS):
            for enemy in context.all_enemies:
                if enemy.is_alive():
                    effects.append(InstantDamage(
                        source=context.source, target=enemy, amount=self.DAMAGE))
        return effects
