from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.StatusEffects.stored_block import StoredBlock


class Prolong(Card):
    def __init__(self):
        super().__init__(
            card_id = "prolong",
            name = "Prolong",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        # Snapshot now: "equal to your current Block" is read when the card is
        # played, not when it pays out next turn.
        return [StoredBlock(source=context.source, target=context.source,
                            amount=context.source.block)]
