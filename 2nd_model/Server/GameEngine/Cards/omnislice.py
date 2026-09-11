from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class Omnislice(Card):
    DAMAGE = 8

    def __init__(self):
        super().__init__(
            card_id = "omnislice",
            name = "Omnislice",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        return [InstantDamage(
            source=context.source, target=context.target, amount=self.DAMAGE)]

    def follow_up(self, result, context):
        dealt = result.get("total", 0)
        if result["effect_id"] != "instant_damage" or dealt <= 0:
            return None
        # The splash is its own damage, so Strength does not get counted twice.
        return [
            InstantDamage(source=context.source, target=enemy, amount=dealt,
                          is_attack=False)
            for enemy in context.all_enemies
            if enemy.is_alive() and enemy is not context.target
        ]
