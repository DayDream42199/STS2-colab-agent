from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.automation import Automation as AutomationStatus


class Automation(Card):
    def __init__(self):
        super().__init__(
            card_id = "automation",
            name = "Automation",
            card_type = CardType.POWER,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [AutomationStatus(
            source=context.source, target=context.source, amount=1)]
