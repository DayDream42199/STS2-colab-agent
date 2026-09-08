from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_block import InstantBlock

class IronWave(Card):
    BLOCK = 5
    DAMAGE = 5

    def __init__(self):
        super().__init__(
            card_id = "iron_wave",
            name = "Iron Wave",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        return [
            InstantBlock(
                source=context.source, target=context.source, amount=self.BLOCK),
            InstantDamage(
                source=context.source, target=context.target, amount=self.DAMAGE),
        ]
