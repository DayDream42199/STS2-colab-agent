from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.strength import Strength
from ..Effects.StatusEffects.dexterity import Dexterity


class Prowess(Card):
    AMOUNT = 1

    def __init__(self):
        super().__init__(
            card_id = "prowess",
            name = "Prowess",
            card_type = CardType.POWER,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [
            Strength(
                source=context.source, target=context.source, amount=self.AMOUNT),
            Dexterity(
                source=context.source, target=context.source, amount=self.AMOUNT),
        ]
