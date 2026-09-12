from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_hp_loss import InstantHpLoss
from ..Effects.InstantEffects.instant_block import InstantBlock


class DemonicShield(Card):
    HP_LOSS = 1

    def __init__(self):
        super().__init__(
            card_id = "demonic_shield",
            name = "Demonic Shield",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.ALLY,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        return [
            InstantHpLoss(
                source=context.source, target=context.source, amount=self.HP_LOSS),
            InstantBlock(source=context.source, target=context.target,
                         amount=context.source.block),
        ]
