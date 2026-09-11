from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.StatusEffects.strength_loss_this_turn import StrengthLossThisTurn


class DarkShackles(Card):
    STRENGTH_LOSS = 9

    def __init__(self):
        super().__init__(
            card_id = "dark_shackles",
            name = "Dark Shackles",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.ENEMY,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        return [StrengthLossThisTurn(
            source=context.source, target=context.target,
            amount=self.STRENGTH_LOSS)]
