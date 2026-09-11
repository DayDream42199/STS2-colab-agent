from ._card import Card
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

        return generatable_card_ids(card_class=CardClass.IRONCLAD)

    def get_effects(self, context):
        ally = context.source
        pool = list(self.offer_from(context))
        if not pool:
            return []
        offer = context.rng.sample(pool, min(self.OFFER, len(pool)))

        def take(chosen):
            ally.free_this_turn.append(chosen)
            return [InstantAddCard(
                source=ally, target=ally, card_id=chosen,
                pile=InstantAddCard.HAND)]

        context.ask(ally, "Choose a card to add to your Hand", offer, take)
        return []
