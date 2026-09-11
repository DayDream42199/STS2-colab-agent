from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_block import InstantBlock
from ..Effects.StatusEffects.delayed_draw import DelayedDraw
from ..Effects.StatusEffects.delayed_energy import DelayedEnergy


class Relax(Card):
    BLOCK = 16
    TURNS = 1

    def __init__(self):
        super().__init__(
            card_id = "relax",
            name = "Relax",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.ANCIENT,
            cost = 3,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        return [
            InstantBlock(
                source=context.source, target=context.source, amount=self.BLOCK),
            DelayedDraw(
                source=context.source, target=context.source, amount=self.TURNS),
            DelayedEnergy(
                source=context.source, target=context.source, amount=self.TURNS),
        ]
