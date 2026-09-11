from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_block import InstantBlock
from ..Effects.StatusEffects.block_lockout import BlockLockout


class PanicButton(Card):
    BLOCK = 30
    TURNS = 2

    def __init__(self):
        super().__init__(
            card_id = "panic_button",
            name = "Panic Button",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        # Block first: the lockout resolves after it, so the card does not
        # cancel its own 30.
        return [
            InstantBlock(
                source=context.source, target=context.source, amount=self.BLOCK),
            BlockLockout(
                source=context.source, target=context.source, amount=self.TURNS),
        ]
