from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_add_card import InstantAddCard


class JackOfAllTrades(Card):
    COUNT = 1

    def __init__(self):
        super().__init__(
            card_id = "jack_of_all_trades",
            name = "Jack of All Trades",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        # Imported here, not at module level: the registry imports
        # this card, so importing it back at import time would deadlock.
        from ..Registry.card_registry import generatable_card_ids

        pool = generatable_card_ids(card_class=CardClass.COLORLESS)
        if not pool:
            return []
        return [
            InstantAddCard(
                source=context.source, target=context.source,
                card_id=context.rng.choice(pool), pile=InstantAddCard.HAND)
            for _ in range(self.COUNT)
        ]
