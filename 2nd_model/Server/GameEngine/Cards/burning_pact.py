from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_exhaust import InstantExhaust
from ..Effects.InstantEffects.instant_draw import InstantDraw


class BurningPact(Card):
    CARDS = 2

    def __init__(self):
        super().__init__(
            card_id = "burning_pact",
            name = "Burning Pact",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        # Picked here rather than in the resolver, so the card owns the choice.
        hand = list(context.source.hand)
        picked = [context.rng.choice(hand)] if hand else []
        return [
            InstantExhaust(
                source=context.source, target=context.source, card_ids=picked),
            InstantDraw(source=context.source, target=context.source,
                        amount=self.CARDS, rng=context.rng),
        ]
