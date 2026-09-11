from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_add_card import InstantAddCard


class InfernalBlade(Card):
    def __init__(self):
        super().__init__(
            card_id = "infernal_blade",
            name = "Infernal Blade",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        # Imported here, not at module level: the registry imports
        # this card, so importing it back at import time would deadlock.
        from ..Registry.card_registry import generatable_card_ids

        pool = generatable_card_ids(
            card_class=CardClass.IRONCLAD, card_type=CardType.ATTACK)
        if not pool:
            return []
        picked = context.rng.choice(pool)
        # Granted here rather than through an effect, the way Equilibrium sets
        # retain_hand: the card already knows which id it is adding.
        context.source.free_this_turn.append(picked)
        return [InstantAddCard(
            source=context.source, target=context.source,
            card_id=picked, pile=InstantAddCard.HAND)]
