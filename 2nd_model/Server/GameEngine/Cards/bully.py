from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class Bully(Card):
    DAMAGE = 4
    EXTRA_PER_VULNERABLE = 2

    def __init__(self):
        super().__init__(
            card_id = "bully",
            name = "Bully",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        vulnerable = context.target.get_status("vulnerable")
        stacks = vulnerable.amount if vulnerable else 0
        return [InstantDamage(
            source=context.source,
            target=context.target,
            amount=self.DAMAGE + self.EXTRA_PER_VULNERABLE * stacks,
        )]
