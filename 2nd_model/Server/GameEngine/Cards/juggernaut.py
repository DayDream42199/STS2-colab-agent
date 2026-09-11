from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.juggernaut import Juggernaut as JuggernautStatus


class Juggernaut(Card):
    AMOUNT = 5

    def __init__(self):
        super().__init__(
            card_id = "juggernaut",
            name = "Juggernaut",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 2,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [
            JuggernautStatus(
                source=context.source, target=context.source, amount=self.AMOUNT),
        ]
