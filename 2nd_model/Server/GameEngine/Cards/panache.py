from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.panache import Panache as PanacheStatus


class Panache(Card):
    def __init__(self):
        super().__init__(
            card_id = "panache",
            name = "Panache",
            card_type = CardType.POWER,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [PanacheStatus(
            source=context.source, target=context.source, amount=1)]
