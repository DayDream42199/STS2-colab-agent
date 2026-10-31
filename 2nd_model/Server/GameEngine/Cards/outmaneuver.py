from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.delayed_energy import DelayedEnergy


class Outmaneuver(Card):
    ENERGY = 2

    def __init__(self):
        super().__init__(
            card_id = "outmaneuver",
            name = "Outmaneuver",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.EVENT,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [DelayedEnergy(
            source=context.source, target=context.source, amount=self.ENERGY)]
