from ._card import Card
from ._card_enums import CardType, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage

class Strike(Card):
    def __init__(self):
        super().__init__(
            card_id = "strike",
            name = "Strike",
            card_type = CardType.ATTACK,
            rarity = CardRarity.BASIC,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        return [
            InstantDamage(
                source=context.source,
                target=context.target,
                amount=6
            )
        ]