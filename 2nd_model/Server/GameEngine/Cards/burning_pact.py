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
        ally = context.source
        draw = InstantDraw(source=ally, target=ally, amount=self.CARDS, rng=context.rngs.shuffle)
        if not ally.hand:
            return [draw]

        # The draw belongs inside the answer: the game exhausts first, so the
        # cards drawn cannot be the one exhausted.
        def exhaust(chosen):
            return [InstantExhaust(source=ally, target=ally, card_ids=[chosen]), draw]

        context.ask(ally, "Exhaust a card", lambda: list(ally.hand), exhaust)
        return []
