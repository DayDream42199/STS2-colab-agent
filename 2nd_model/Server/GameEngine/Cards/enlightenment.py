from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_cap_cost import InstantCapCost


class Enlightenment(Card):
    def __init__(self):
        super().__init__(
            card_id = "enlightenment",
            name = "Enlightenment",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.EVENT,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        # The cards in hand now, each copy capped at 1: this turn or until it
        # is played, or for the rest of the combat upgraded - the game's
        # EnergyCost.SetThisTurnOrUntilPlayed / SetThisCombat(1, reduceOnly).
        # A card drawn afterwards costs what it costs.
        if not context.source.hand:
            return []
        return [InstantCapCost(
            source=context.source, target=context.source,
            card_refs=list(context.source.hand), amount=1,
            this_combat=self.upgraded)]
