from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_draw import InstantDraw


class Impatience(Card):
    CARDS = 2

    def __init__(self):
        super().__init__(
            card_id = "impatience",
            name = "Impatience",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        # Imported here, not at module level: card_registry imports this
        # module, so a top-level import would be circular.
        from ..Registry.card_registry import create_card
        for card_id in context.source.hand:
            if create_card(card_id).card_type is CardType.ATTACK:
                return []
        return [InstantDraw(source=context.source, target=context.source,
                            amount=self.CARDS, rng=context.rng)]
