from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.StatusEffects.enlightenment import Enlightenment as EnlightenmentStatus


class Enlightenment(Card):
    def __init__(self):
        super().__init__(
            card_id = "enlightenment",
            name = "Enlightenment",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        # A status rather than a per-card rewrite: piles hold id strings, so
        # there is no per-copy cost to set. Capping every card the owner plays
        # this turn is the same thing for a hand you cannot add to for free.
        return [EnlightenmentStatus(
            source=context.source, target=context.source, amount=1)]
