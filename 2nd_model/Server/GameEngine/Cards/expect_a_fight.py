from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock


class ExpectAFight(Card):
    BLOCK = 15
    EXTRA_PER_STRENGTH = 5

    def __init__(self):
        super().__init__(
            card_id = "expect_a_fight",
            name = "Expect a Fight",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 2,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        strength = context.source.get_status("strength")
        stacks = strength.amount if strength else 0
        return [InstantBlock(
            source=context.source,
            target=context.source,
            amount=self.BLOCK + self.EXTRA_PER_STRENGTH * stacks,
        )]
