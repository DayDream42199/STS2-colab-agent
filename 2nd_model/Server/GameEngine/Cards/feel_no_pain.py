from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.feel_no_pain import FeelNoPain as FeelNoPainStatus


class FeelNoPain(Card):
    AMOUNT = 3

    def __init__(self):
        super().__init__(
            card_id = "feel_no_pain",
            name = "Feel No Pain",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [
            FeelNoPainStatus(
                source=context.source, target=context.source, amount=self.AMOUNT),
        ]
