from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_play_card import InstantPlayCard


class Catastrophe(Card):
    COUNT = 2

    def __init__(self):
        super().__init__(
            card_id = "catastrophe",
            name = "Catastrophe",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 2,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        draw = list(context.source.draw_pile)
        if not draw:
            return []
        picked = (draw if len(draw) <= self.COUNT
                  else context.rng.sample(draw, self.COUNT))
        return [
            InstantPlayCard(source=context.source, target=context.source,
                            card_id=card_id, from_pile=InstantPlayCard.DRAW)
            for card_id in picked
        ]
