from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType


class Enthralled(Card):
    # Combat reads this off the hand: nothing else may be played while it is
    # held. Unlike the other curses it is playable, because playing it is the
    # only way out.
    MUST_PLAY_FIRST = True

    def __init__(self):
        super().__init__(
            card_id = "enthralled",
            name = "Enthralled",
            card_type = CardType.CURSE,
            card_class = CardClass.CURSE,
            rarity = CardRarity.COMMON,
            cost = 2,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return []   # playing it does nothing but get rid of it
