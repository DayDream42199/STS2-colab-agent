from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_energy import InstantEnergy


class BelieveInYou(Card):
    ENERGY = 2

    def __init__(self):
        super().__init__(
            card_id = "believe_in_you",
            name = "Believe in You",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.ALLY
        )

    def get_effects(self, context):
        if context.target is context.source:
            raise ValueError(f"{self.name} must target another player.")
        return [InstantEnergy(
            source=context.source, target=context.target, amount=self.ENERGY)]
