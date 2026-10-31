from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock
from ..Effects.StatusEffects.delayed_block import DelayedBlock


class ToricToughness(Card):
    BLOCK = 5
    TURNS = 2

    def __init__(self):
        super().__init__(
            card_id = "toric_toughness",
            name = "Toric Toughness",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.EVENT,
            cost = 2,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [InstantBlock(
            source=context.source, target=context.source, amount=self.BLOCK)]

    def follow_up(self, result, context):
        # Once the Block is gained, the next turns get that same amount - what
        # was really gained, after Dexterity and Frail - as the game's
        # ToricToughnessPower.SetBlock(blockAmount) does.
        if result["effect_id"] != "instant_block" or result["target_id"] != context.source.unit_id:
            return None
        return [DelayedBlock(source=context.source, target=context.source,
                             amount=self.TURNS, block=result["amount"])]
