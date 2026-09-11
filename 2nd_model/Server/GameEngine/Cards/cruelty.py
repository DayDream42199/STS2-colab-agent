from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.cruelty import Cruelty as CrueltyStatus


class Cruelty(Card):
    def __init__(self):
        super().__init__(
            card_id = "cruelty",
            name = "Cruelty",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [CrueltyStatus(
            source=context.source, target=context.source, amount=1)]
