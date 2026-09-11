from ._card import Card
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
        # A plain counter on the ally, like retain_hand: Combat spends it in
        # _extra_plays when the next Attack is played.
        context.source.extra_attack_plays += self.REPLAYS
        return []
