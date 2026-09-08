from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.strength_this_turn import StrengthThisTurn

class Coordinate(Card):
    STRENGTH = 5

    def __init__(self):
        super().__init__(
            card_id = "coordinate",
            name = "Coordinate",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ALLY
        )

    def get_effects(self, context):
        if context.target is context.source:
            raise ValueError(f"{self.name} must target another player.")
        # Co-op card: the Strength goes to the chosen ally, not to the caster.
        return [StrengthThisTurn(
            source=context.source, target=context.target, amount=self.STRENGTH)]
