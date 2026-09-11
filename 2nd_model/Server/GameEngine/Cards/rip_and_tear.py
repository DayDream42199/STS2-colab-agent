from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class RipAndTear(Card):
    DAMAGE = 7
    HITS = 2

    def __init__(self):
        super().__init__(
            card_id = "rip_and_tear",
            name = "Rip and Tear",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.RANDOM_ENEMY
        )

    def get_effects(self, context):
        # Re-rolled per hit, so the two hits can land on different enemies.
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
