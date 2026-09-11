from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.strength_this_turn import StrengthThisTurn


class FeedingFrenzy(Card):
    STRENGTH = 5

    def __init__(self):
        super().__init__(
            card_id = "feeding_frenzy",
            name = "Feeding Frenzy",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [StrengthThisTurn(
            source=context.source, target=context.source, amount=self.STRENGTH)]
