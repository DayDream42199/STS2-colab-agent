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

    def get_effects(self, context):
        exhausted = len(context.source.exhaust_pile)
        return [InstantDamage(
            source=context.source,
            target=context.target,
            amount=self.DAMAGE + self.EXTRA_PER_EXHAUSTED * exhausted,
        )]
