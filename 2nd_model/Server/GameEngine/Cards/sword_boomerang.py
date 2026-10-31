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
        # hits can land on different enemies. One at a time: each hit picks
        # from the enemies still standing once the last one has landed, as
        # the game's AttackCommand does, so none is spent on a corpse.
        for hit in range(self.HITS):
            alive = [e for e in context.all_enemies if e.is_alive()]
            if not alive:
                return
            effect = InstantDamage(
                source=context.source,
                target=context.rngs.targets.choice(alive),
                amount=self.DAMAGE,
            )
            effect.hit = hit           # its own hit, whoever it lands on (Combat._Hits)
            yield effect
