from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ._card_ref import is_upgraded
from ..Effects.InstantEffects.instant_upgrade_card import InstantUpgradeCard


class Apotheosis(Card):
    def __init__(self):
        super().__init__(
            card_id = "apotheosis",
            name = "Apotheosis",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.ANCIENT,
            cost = 2,
            target_type = TargetType.SELF,
            properties = CardProperties(innate=True, exhaust=True)
        )

    def get_effects(self, context):
        ally = context.source
        # Not the exhaust pile: those cards are out of the fight.
        everything = [ref
                      for pile in (ally.hand, ally.draw_pile, ally.discard_pile)
                      for ref in pile if not is_upgraded(ref)]
        return [InstantUpgradeCard(
            source=ally, target=ally, card_refs=everything)]
