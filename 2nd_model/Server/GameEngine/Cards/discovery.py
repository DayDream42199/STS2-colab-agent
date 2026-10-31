from ._card import Card
from ._card_ref import free_copy
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_add_card import InstantAddCard


class Discovery(Card):
    OFFER = 3

    def __init__(self):
        super().__init__(
            card_id = "discovery",
            name = "Discovery",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def offer_from(self, context):
        from ..Registry.card_registry import generatable_card_ids

        return generatable_card_ids(card_class=CardClass.IRONCLAD, solo=context.solo)

    def get_effects(self, context):
        ally = context.source
        pool = list(self.offer_from(context))
        if not pool:
            return []
        offer = context.rngs.card_generation.sample(pool, min(self.OFFER, len(pool)))
        offer = [self.offered(card_id) for card_id in offer]

        def take(chosen):
            return [InstantAddCard(
                source=ally, target=ally, card_id=free_copy(chosen),
                pile=InstantAddCard.HAND)]

        # canSkip, as the game's choose-a-card screen: taking none is allowed.
        context.ask(ally, "Choose a card to add to your Hand", offer, take,
                    can_stop=True)
        return []

    def offered(self, card_id):
        """The copy put on offer for `card_id`."""
        return card_id
