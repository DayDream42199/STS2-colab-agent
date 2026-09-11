from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock


class Rally(Card):
    BLOCK = 12

    def __init__(self):
        super().__init__(
            card_id = "rally",
            name = "Rally",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 2,
            target_type = TargetType.ALL_ALLIES
        )

    def get_effects(self, context):
        # ALL players, the caster included.
        return [
            InstantBlock(source=context.source, target=ally, amount=self.BLOCK)
            for ally in context.all_allies
            if ally.is_alive()
        ]
