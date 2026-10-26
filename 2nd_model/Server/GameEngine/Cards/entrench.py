from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock


class Entrench(Card):
    def __init__(self):
        super().__init__(
            card_id = "entrench",
            name = "Entrench",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 2,
            target_type = TargetType.SELF
        )

    def base_block(self, ally):
        # Read live: doubling means granting again whatever we already hold.
        return ally.block

    def block_gains(self, ally):
        # Unpowered in the game (ValueProp.Unpowered): Dexterity and Frail do
        # not touch the doubling. Unmovable still does.
        return [(self.base_block(ally), False)]

    def get_effects(self, context):
        return [InstantBlock(
            source=context.source,
            target=context.source,
            amount=self.base_block(context.source),
            powered=False,
        )]
