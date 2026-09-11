from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.StatusEffects.strength_loss_this_turn import StrengthLossThisTurn


class Mangle(Card):
    DAMAGE = 20
    STRENGTH_LOSS = 10

    def __init__(self):
        super().__init__(
            card_id = "mangle",
            name = "Mangle",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 3,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        return [
            InstantDamage(
                source=context.source, target=context.target, amount=self.DAMAGE),
            StrengthLossThisTurn(source=context.source, target=context.target,
                                 amount=self.STRENGTH_LOSS),
        ]
