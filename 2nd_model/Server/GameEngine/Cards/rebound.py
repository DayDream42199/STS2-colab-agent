from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.StatusEffects.rebound import Rebound as ReboundStatus


class Rebound(Card):
    DAMAGE = 9

    def __init__(self):
        super().__init__(
            card_id = "rebound",
            name = "Rebound",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        return [
            InstantDamage(
                source=context.source, target=context.target, amount=self.DAMAGE),
            ReboundStatus(
                source=context.source, target=context.source, amount=1),
        ]
