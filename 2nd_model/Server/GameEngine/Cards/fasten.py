from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.fasten import Fasten as FastenStatus


class Fasten(Card):
    BLOCK = 4

    def __init__(self):
        super().__init__(
            card_id = "fasten",
            name = "Fasten",
            card_type = CardType.POWER,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def base_block(self, ally):
        # BLOCK is what the power adds to Defends, not Block for the player.
        return None

    def get_effects(self, context):
        return [FastenStatus(
            source=context.source, target=context.source, amount=self.BLOCK)]
