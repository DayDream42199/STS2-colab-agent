from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class Rend(Card):
    DAMAGE = 10
    PER_DEBUFF = 5

    def __init__(self):
        super().__init__(
            card_id = "rend",
            name = "Rend",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        # Unique debuffs, not stacks: 3 Vulnerable counts once.
        debuffs = sum(
            1 for status in context.target.statuses.values()
            if status.IS_DEBUFF and status.amount > 0
        )
        return [InstantDamage(
            source=context.source,
            target=context.target,
            amount=self.DAMAGE + debuffs * self.PER_DEBUFF,
        )]
