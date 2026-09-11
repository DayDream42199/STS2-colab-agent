from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.stratagem import Stratagem as StratagemStatus


class Stratagem(Card):
    def __init__(self):
        super().__init__(
            card_id = "stratagem",
            name = "Stratagem",
            card_type = CardType.POWER,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [StratagemStatus(
            source=context.source, target=context.source, amount=1)]
