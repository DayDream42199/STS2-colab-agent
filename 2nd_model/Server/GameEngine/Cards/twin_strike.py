from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage

class TwinStrike(Card):
    DAMAGE = 5
    HITS = 2

    def __init__(self):
        super().__init__(
            card_id = "twin_strike",
            name = "Twin Strike",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        # Two separate instances, not one of double size: each is rolled
        # through block and modifiers on its own.
        return [
            InstantDamage(
                source=context.source, target=context.target, amount=self.DAMAGE)
            for _ in range(self.HITS)
        ]
