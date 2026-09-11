from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock
from ..Effects.StatusEffects.vulnerable import Vulnerable

class Taunt(Card):
    BLOCK = 6
    VULNERABLE = 1

    def __init__(self):
        super().__init__(
            card_id = "taunt",
            name = "Taunt",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        # Block lands on us, the debuff on the enemy we picked.
        return [
            InstantBlock(
                source=context.source, target=context.source, amount=self.BLOCK),
            Vulnerable(
                source=context.source, target=context.target, amount=self.VULNERABLE),
        ]
