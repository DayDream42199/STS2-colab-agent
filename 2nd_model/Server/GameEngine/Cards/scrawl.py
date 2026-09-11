from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_draw import InstantDraw


class Scrawl(Card):
    def __init__(self):
        super().__init__(
            card_id = "scrawl",
            name = "Scrawl",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        # Ally.HAND_LIMIT is what "full" means, and drawing stops there anyway;
        # asking only for the difference keeps the reported count honest.
        missing = context.source.HAND_LIMIT - len(context.source.hand)
        if missing <= 0:
            return []
        return [InstantDraw(source=context.source, target=context.source,
                            amount=missing, rng=context.rng)]
