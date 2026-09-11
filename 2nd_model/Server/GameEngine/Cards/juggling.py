from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.juggling import Juggling as JugglingStatus


class Juggling(Card):
    def __init__(self):
        super().__init__(
            card_id = "juggling",
            name = "Juggling",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [JugglingStatus(
            source=context.source, target=context.source, amount=1)]
