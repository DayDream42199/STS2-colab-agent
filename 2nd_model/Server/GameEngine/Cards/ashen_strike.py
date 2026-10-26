from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class AshenStrike(Card):
    DAMAGE = 6
    EXTRA_PER_EXHAUSTED = 3

    def __init__(self):
        super().__init__(
            card_id = "ashen_strike",
            name = "Ashen Strike",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def base_damage(self, ally):
        return self.DAMAGE + self.EXTRA_PER_EXHAUSTED * len(ally.exhaust_pile)

    def get_effects(self, context):
        return [InstantDamage(
            source=context.source,
            target=context.target,
            amount=self.base_damage(context.source),
        )]
