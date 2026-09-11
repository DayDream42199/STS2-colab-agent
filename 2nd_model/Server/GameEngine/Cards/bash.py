from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.StatusEffects.vulnerable import Vulnerable

class Bash(Card):
    DAMAGE = 8
    VULNERABLE = 2

    def __init__(self):
        super().__init__(
            card_id = "bash",
            name = "Bash",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.BASIC,
            cost = 2,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        return [
            InstantDamage(
                source=context.source,
                target=context.target,
                amount=self.DAMAGE
            ),
            Vulnerable(
                source=context.source,
                target=context.target,
                amount=self.VULNERABLE
            )
        ]