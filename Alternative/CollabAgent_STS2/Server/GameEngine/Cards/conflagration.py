from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage

class Conflagration(Card):
    DAMAGE = 2
    ROUNDS = 4

    def __init__(self):
        super().__init__(
            card_id = "conflagration",
            name = "Conflagration",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 1,
            target_type = TargetType.ALL_ENEMIES
        )

    def get_effects(self, context):
        # Four passes over the party, not one pass of quadruple damage: each
        # hit meets block on its own.
        effects = []
        for _ in range(self.ROUNDS):
            for enemy in context.all_enemies:
                if enemy.is_alive():
                    effects.append(InstantDamage(
                        source=context.source, target=enemy, amount=self.DAMAGE))
        return effects
