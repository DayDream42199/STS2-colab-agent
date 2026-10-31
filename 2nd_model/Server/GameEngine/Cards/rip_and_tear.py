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
            rarity = CardRarity.EVENT,
            cost = 1,
            target_type = TargetType.RANDOM_ENEMY
        )

    def get_effects(self, context):
        # Re-rolled per hit, so the two hits can land on different enemies.
        # One at a time: each hit picks from the enemies still standing once
        # the last one has landed, as the game's AttackCommand does.
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
