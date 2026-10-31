from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock
from ..Effects.StatusEffects.intercepting import Intercepting


class Intercept(Card):
    MULTIPLAYER_ONLY = True         # a co-op card: not made at random solo
    BLOCK = 9

    def __init__(self):
        super().__init__(
            card_id = "intercept",
            name = "Intercept",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ALLY
        )

    def get_effects(self, context):
        return [
            InstantBlock(
                source=context.source, target=context.source, amount=self.BLOCK),
            # The chosen player is covered; the one covering is this one.
            Intercepting(
                source=context.source, target=context.source, amount=1,
                covered=context.target),
        ]
