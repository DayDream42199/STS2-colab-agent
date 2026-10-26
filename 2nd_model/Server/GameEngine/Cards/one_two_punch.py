from ._card import Card
from ..Effects.StatusEffects.one_two_punch import OneTwoPunch as OneTwoPunchStatus
from ._card_enums import CardType, CardClass, CardRarity, TargetType


class OneTwoPunch(Card):
    REPLAYS = 1

    def __init__(self):
        super().__init__(
            card_id = "one_two_punch",
            name = "One-Two Punch",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        # The game's OneTwoPunchPower: a status for this turn, spent one
        # charge per Attack by Combat._extra_plays.
        return [OneTwoPunchStatus(
            source=context.source, target=context.source, amount=self.REPLAYS)]
