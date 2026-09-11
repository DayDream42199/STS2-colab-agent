from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class PactsEnd(Card):
    DAMAGE = 18
    REQUIRED_EXHAUSTED = 3

    def __init__(self):
        super().__init__(
            card_id = "pacts_end",
            name = "Pact's End",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 0,
            target_type = TargetType.ALL_ENEMIES
        )

    def get_effects(self, context):
        if len(context.source.exhaust_pile) < self.REQUIRED_EXHAUSTED:
            return []
        return [
            InstantDamage(source=context.source, target=enemy, amount=self.DAMAGE)
            for enemy in context.all_enemies
            if enemy.is_alive()
        ]
