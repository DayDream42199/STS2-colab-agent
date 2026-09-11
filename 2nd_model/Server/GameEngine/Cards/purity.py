from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_exhaust import InstantExhaust


class Purity(Card):
    COUNT = 3

    def __init__(self):
        super().__init__(
            card_id = "purity",
            name = "Purity",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True, retain=True)
        )

    def get_effects(self, context):
        # "Up to 3" is asked one card at a time: each answer queues the next
        # question over what is left, so nothing can be picked twice. Purity
        # itself has already left the hand, so it cannot pick itself.
        ally = context.source

        def ask(left):
            if left <= 0 or not ally.hand:
                return

            def exhaust(chosen):
                ask(left - 1)
                return [InstantExhaust(
                    source=ally, target=ally, card_ids=[chosen])]

            context.ask(ally, f"Exhaust a card ({left} left)",
                        lambda: list(ally.hand), exhaust)

        ask(self.COUNT)
        return []
