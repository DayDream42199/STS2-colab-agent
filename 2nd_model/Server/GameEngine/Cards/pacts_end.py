from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class PactsEnd(Card):
    DAMAGE = 17
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

    def base_damage(self, ally):
        # Playable either way, as in the game; it only hits with 3+ cards in
        # the exhaust pile (where the game makes it glow gold), so 0 before.
        if len(ally.exhaust_pile) < self.REQUIRED_EXHAUSTED:
            return 0
        return self.DAMAGE

    def get_effects(self, context):
        damage = self.base_damage(context.source)
        if not damage:
            return []
        return [
            InstantDamage(source=context.source, target=enemy, amount=damage)
            for enemy in context.all_enemies
            if enemy.is_alive()
        ]
