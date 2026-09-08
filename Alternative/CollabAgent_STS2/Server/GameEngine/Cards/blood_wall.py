from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_hp_loss import InstantHpLoss
from ..Effects.InstantEffects.instant_block import InstantBlock

class BloodWall(Card):
    HP_LOSS = 2
    BLOCK = 16

    def __init__(self):
        super().__init__(
            card_id = "blood_wall",
            name = "Blood Wall",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.COMMON,
            cost = 2,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [
            InstantHpLoss(
                source=context.source, target=context.source, amount=self.HP_LOSS),
            InstantBlock(
                source=context.source, target=context.source, amount=self.BLOCK),
        ]
