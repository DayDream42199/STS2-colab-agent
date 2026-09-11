from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class Whirlwind(Card):
    DAMAGE = 5

    def __init__(self):
        super().__init__(
            card_id = "whirlwind",
            name = "Whirlwind",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = Card.X_COST,
            target_type = TargetType.ALL_ENEMIES
        )

    def get_effects(self, context):
        effects = []
        for _ in range(context.x_amount):
            for enemy in context.all_enemies:
                if enemy.is_alive():
                    effects.append(InstantDamage(
                        source=context.source, target=enemy,
                        amount=self.DAMAGE))
        return effects
