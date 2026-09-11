from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock
from ..Effects.StatusEffects.gambit import Gambit


class TheGambit(Card):
    BLOCK = 50

    def __init__(self):
        super().__init__(
            card_id = "the_gambit",
            name = "The Gambit",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [
            InstantBlock(
                source=context.source, target=context.source, amount=self.BLOCK),
            Gambit(source=context.source, target=context.source, amount=1),
        ]
