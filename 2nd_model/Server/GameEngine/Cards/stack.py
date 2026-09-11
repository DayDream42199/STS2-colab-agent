from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock


class Stack(Card):
    # Upgraded, Stack counts three cards that are not there.
    BONUS = 0

    def __init__(self):
        super().__init__(
            card_id = "stack",
            name = "Stack",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [InstantBlock(
            source=context.source,
            target=context.source,
            amount=len(context.source.discard_pile) + self.BONUS,
        )]
