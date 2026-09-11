from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock


class EvilEye(Card):
    BLOCK = 8

    def __init__(self):
        super().__init__(
            card_id = "evil_eye",
            name = "Evil Eye",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        total = self.BLOCK
        if context.source.turn_count("cards_exhausted"):
            total += self.BLOCK
        return [InstantBlock(
            source=context.source, target=context.source, amount=total)]
