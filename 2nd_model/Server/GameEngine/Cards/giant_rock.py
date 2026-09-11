from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class GiantRock(Card):
    DAMAGE = 20

    def __init__(self):
        super().__init__(
            card_id = "giant_rock",
            name = "Giant Rock",
            card_type = CardType.ATTACK,
            card_class = CardClass.TOKEN,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        return [InstantDamage(
            source=context.source, target=context.target, amount=self.DAMAGE)]
