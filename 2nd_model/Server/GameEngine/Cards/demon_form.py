from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.demon_form import DemonForm as DemonFormStatus


class DemonForm(Card):
    AMOUNT = 3

    def __init__(self):
        super().__init__(
            card_id = "demon_form",
            name = "Demon Form",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 3,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [
            DemonFormStatus(
                source=context.source, target=context.source, amount=self.AMOUNT),
        ]
