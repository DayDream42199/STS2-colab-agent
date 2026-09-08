from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage

class SwordBoomerang(Card):
    DAMAGE = 3
    HITS = 3

    def __init__(self):
        super().__init__(
            card_id = "sword_boomerang",
            name = "Sword Boomerang",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.RANDOM_ENEMY
        )

    def get_effects(self, context):
        # Re-rolled per hit rather than using context.target, so the three
        # hits can land on different enemies.
        effects = []
        for _ in range(self.HITS):
            alive = [e for e in context.all_enemies if e.is_alive()]
            if not alive:
                break
            effects.append(InstantDamage(
                source=context.source,
                target=context.rng.choice(alive),
                amount=self.DAMAGE,
            ))
        return effects
