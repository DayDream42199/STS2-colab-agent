from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.StatusEffects.exposed import Exposed


class Knockdown(Card):
    MULTIPLAYER_ONLY = True         # a co-op card: not made at random solo
    DAMAGE = 10
    KNOCKDOWN = 2                   # the damage multiplier for the others

    def __init__(self):
        super().__init__(
            card_id = "knockdown",
            name = "Knockdown",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.RARE,
            cost = 3,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        return [
            InstantDamage(
                source=context.source, target=context.target, amount=self.DAMAGE),
            Exposed(source=context.source, target=context.target,
                    amount=self.KNOCKDOWN),
        ]
