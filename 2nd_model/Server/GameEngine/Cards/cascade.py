from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_play_card import InstantPlayCard


class Cascade(Card):
    def __init__(self):
        super().__init__(
            card_id = "cascade",
            name = "Cascade",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = Card.X_COST,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        draw = context.source.draw_pile
        # The pile is drawn from the end, so the last X entries are the top X,
        # and they are played from the top down.
        top = draw[-context.x_amount:] if context.x_amount else []
        return [
            InstantPlayCard(source=context.source, target=context.source,
                            card_id=card_id,
                            from_pile=InstantPlayCard.DRAW)
            for card_id in reversed(top)
        ]
