from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.beacon_of_hope import BeaconOfHope as BeaconOfHopeStatus


class BeaconOfHope(Card):
    MULTIPLAYER_ONLY = True         # a co-op card: not made at random solo
    def __init__(self):
        super().__init__(
            card_id = "beacon_of_hope",
            name = "Beacon of Hope",
            card_type = CardType.POWER,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.RARE,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [BeaconOfHopeStatus(
            source=context.source, target=context.source, amount=1)]
