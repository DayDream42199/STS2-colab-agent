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
        draw = context.source.draw_pile
        if not draw:
            return []
        # The pile is drawn from the end, so the last entry is the top card.
        return [InstantPlayCard(
            source=context.source, target=context.source,
            card_id=draw[-1], from_pile=InstantPlayCard.DRAW,
            force_exhaust=True)]
