from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock
from ..Effects.InstantEffects.instant_exhaust import InstantExhaust


class TrueGrit(Card):
    BLOCK = 7

    def __init__(self):
        super().__init__(
            card_id = "true_grit",
            name = "True Grit",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        # Picked here rather than in the resolver, so the card owns the choice.
        hand = list(context.source.hand)
        picked = [context.rng.choice(hand)] if hand else []
        return [
            InstantBlock(
                source=context.source, target=context.source, amount=self.BLOCK),
            InstantExhaust(
                source=context.source, target=context.source, card_ids=picked),
        ]
