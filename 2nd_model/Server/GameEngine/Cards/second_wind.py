from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock
from ..Effects.InstantEffects.instant_exhaust import InstantExhaust


class SecondWind(Card):
    BLOCK_PER_CARD = 5

    def __init__(self):
        super().__init__(
            card_id = "second_wind",
            name = "Second Wind",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        from ..Registry.card_registry import create_card
        # Attacks stay; everything else burns.
        doomed = [c for c in context.source.hand
                  if create_card(c).card_type is not CardType.ATTACK]
        if not doomed:
            return []
        return [
            InstantExhaust(
                source=context.source, target=context.source, card_ids=doomed),
            InstantBlock(source=context.source, target=context.source,
                         amount=self.BLOCK_PER_CARD * len(doomed)),
        ]
