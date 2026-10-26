from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_play_card import InstantPlayCard


class Havoc(Card):
    def __init__(self):
        super().__init__(
            card_id = "havoc",
            name = "Havoc",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        # "The top card", picked when it resolves: Combat shuffles the discard
        # in first if the draw pile is empty, as the game does.
        return [InstantPlayCard(
            source=context.source, target=context.source, card_id=None,
            from_pile=InstantPlayCard.DRAW, count=1, force_exhaust=True)]
