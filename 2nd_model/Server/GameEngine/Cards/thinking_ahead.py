from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_draw import InstantDraw
from ..Effects.InstantEffects.instant_move_card import InstantMoveCard


class ThinkingAhead(Card):
    CARDS = 2

    def __init__(self):
        super().__init__(
            card_id = "thinking_ahead",
            name = "Thinking Ahead",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        return [InstantDraw(
            source=context.source, target=context.source,
            amount=self.CARDS, rng=context.rng)]

    def follow_up(self, result, context):
        # The question can only be put once the draw has happened, so it is
        # asked here rather than up front. Combat holds it until the card is
        # done, which is why this returns no effects of its own.
        if result["effect_id"] != "instant_draw":
            return None
        ally = context.source
        if not ally.hand:
            return None

        def stash(chosen):
            return [InstantMoveCard(
                source=ally, target=ally, card_ids=[chosen],
                from_pile=InstantMoveCard.HAND,
                to_pile=InstantMoveCard.DRAW, to_top=True)]

        context.ask(ally, "Put a card on top of your Draw Pile",
                    lambda: list(ally.hand), stash)
        return None
