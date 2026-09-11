from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_add_card import InstantAddCard
from ..Effects.InstantEffects.instant_exhaust import InstantExhaust


class Stoke(Card):
    def __init__(self):
        super().__init__(
            card_id = "stoke",
            name = "Stoke",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        # Imported here, not at module level: the registry imports
        # this card, so importing it back at import time would deadlock.
        from ..Registry.card_registry import generatable_card_ids

        # Stoke has already left the hand, so "your Hand" is what remains.
        hand = list(context.source.hand)
        pool = generatable_card_ids(card_class=CardClass.IRONCLAD)
        if not hand or not pool:
            return []
        effects = [InstantExhaust(
            source=context.source, target=context.source, card_ids=hand)]
        # One roll per exhausted card, so the replacements can repeat.
        effects.extend(
            InstantAddCard(
                source=context.source, target=context.source,
                card_id=context.rng.choice(pool), pile=InstantAddCard.HAND)
            for _ in hand
        )
        return effects
