from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.bomb import Bomb


class TheBomb(Card):
    TURNS = 3

    def __init__(self):
        super().__init__(
            card_id = "the_bomb",
            name = "The Bomb",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 2,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [Bomb(source=context.source, target=context.source,
                     amount=self.TURNS)]
