from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock
from ..Effects.StatusEffects.colossus_guard import ColossusGuard


class Colossus(Card):
    BLOCK = 4

    def __init__(self):
        super().__init__(
            card_id = "colossus",
            name = "Colossus",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [
            InstantBlock(
                source=context.source, target=context.source, amount=self.BLOCK),
            ColossusGuard(
                source=context.source, target=context.source, amount=1),
        ]
