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
        # Upgraded, it plays one more than was paid - X+1 - which lives in
        # the play itself, not in the upgrade table.
        count = context.x_amount + (1 if self.upgraded else 0)
        if count <= 0:
            return []
        return [InstantPlayCard(
            source=context.source, target=context.source, card_id=None,
            from_pile=InstantPlayCard.DRAW, count=count)]
