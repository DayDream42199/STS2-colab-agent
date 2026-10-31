from ._card import Card
from ._card_ref import free_copy
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_add_card import InstantAddCard


class Metamorphosis(Card):
    COUNT = 3

    def __init__(self):
        super().__init__(
            card_id = "metamorphosis",
            name = "Metamorphosis",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.EVENT,
            cost = 2,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        # Imported here, not at module level: the registry imports
        # this card, so importing it back at import time would deadlock.
        from ..Registry.card_registry import generatable_card_ids

        pool = generatable_card_ids(
            card_class=CardClass.IRONCLAD, card_type=CardType.ATTACK,
            solo=context.solo)
        if not pool:
            return []
        effects = []
        for _ in range(self.COUNT):
            picked = context.rngs.card_generation.choice(pool)
            # Free for the combat, every time it is played - not only the first.
            effects.append(InstantAddCard(
                source=context.source, target=context.source,
                card_id=free_copy(picked, this_combat=True),
                pile=InstantAddCard.DRAW, rng=context.rngs.shuffle))
        return effects
