from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from .discovery import Discovery


class Abundance(Discovery):
    """Discovery narrowed to Powers, and to the Ironclad pool - the only pool
    the reference builds its by-type table from."""

    def __init__(self):
        Card.__init__(
            self,
            card_id = "abundance",
            name = "Abundance",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.ANCIENT,
            cost = 1,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def offer_from(self, context):
        from ..Registry.card_registry import generatable_card_ids

        return generatable_card_ids(card_class=CardClass.IRONCLAD,
                                    card_type=CardType.POWER)
