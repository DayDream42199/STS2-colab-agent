from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_draw import InstantDraw
from ..Effects.InstantEffects.instant_energy import InstantEnergy


class Restlessness(Card):
    CARDS = 2
    ENERGY = 2

    def __init__(self):
        super().__init__(
            card_id = "restlessness",
            name = "Restlessness",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(retain=True)
        )

    def get_effects(self, context):
        # This card has already left the hand, so "empty" means nothing else.
        if context.source.hand:
            return []
        return [
            InstantDraw(source=context.source, target=context.source,
                        amount=self.CARDS, rng=context.rng),
            InstantEnergy(source=context.source, target=context.source, amount=self.ENERGY),
        ]
