from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.StatusEffects.strength_this_turn import StrengthThisTurn

class SetupStrike(Card):
    DAMAGE = 7
    STRENGTH = 3

    def __init__(self):
        super().__init__(
            card_id = "setup_strike",
            name = "Setup Strike",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        # The Strength lands on the player, not the enemy being hit.
        return [
            InstantDamage(
                source=context.source, target=context.target, amount=self.DAMAGE),
            StrengthThisTurn(
                source=context.source, target=context.source, amount=self.STRENGTH),
        ]
