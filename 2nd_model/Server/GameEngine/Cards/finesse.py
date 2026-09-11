from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock
from ..Effects.InstantEffects.instant_draw import InstantDraw


class Finesse(Card):
    BLOCK = 4
    CARDS = 1

    def __init__(self):
        super().__init__(
            card_id = "finesse",
            name = "Finesse",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [
            InstantBlock(source=context.source, target=context.source, amount=self.BLOCK),
            InstantDraw(source=context.source, target=context.source,
                        amount=self.CARDS, rng=context.rng),
        ]
