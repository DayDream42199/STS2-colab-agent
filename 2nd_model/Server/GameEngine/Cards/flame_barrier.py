from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock
from ..Effects.StatusEffects.flame_barrier import FlameBarrier as FlameBarrierStatus


class FlameBarrier(Card):
    BLOCK = 12
    AMOUNT = 4

    def __init__(self):
        super().__init__(
            card_id = "flame_barrier",
            name = "Flame Barrier",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 2,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [
            InstantBlock(
                source=context.source, target=context.source, amount=self.BLOCK),
            FlameBarrierStatus(
                source=context.source, target=context.source, amount=self.AMOUNT),
        ]
