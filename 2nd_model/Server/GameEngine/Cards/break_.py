from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.StatusEffects.vulnerable import Vulnerable

class Break(Card):
    DAMAGE = 20
    VULNERABLE = 5

    def __init__(self):
        super().__init__(
            card_id = "break",
            name = "Break",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.ANCIENT,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        return [
            InstantDamage(
                source=context.source, target=context.target, amount=self.DAMAGE),
            Vulnerable(
                source=context.source, target=context.target, amount=self.VULNERABLE),
        ]
