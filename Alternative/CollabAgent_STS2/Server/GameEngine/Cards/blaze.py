from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.strength import Strength

class Blaze(Card):
    STRENGTH = 5

    def __init__(self):
        super().__init__(
            card_id = "blaze",
            name = "Blaze",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 2,
            target_type = TargetType.ALLY
        )

    def get_effects(self, context):
        if context.target is context.source:
            raise ValueError(f"{self.name} must target another player.")
        # Permanent Strength, unlike Coordinate's this-turn version.
        return [Strength(
            source=context.source, target=context.target, amount=self.STRENGTH)]
