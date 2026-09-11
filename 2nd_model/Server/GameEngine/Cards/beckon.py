from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Events.game_event import GameEvent
from ..Effects.InstantEffects.instant_hp_loss import InstantHpLoss


class Beckon(Card):
    AMOUNT = 6

    def __init__(self):
        super().__init__(
            card_id = "beckon",
            name = "Beckon",
            card_type = CardType.STATUS,
            card_class = CardClass.STATUS,
            rarity = CardRarity.COMMON,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(playable=False)
        )

    def on_event(self, event, context):
        # Only while it is still sitting in hand at end of turn.
        if event is not GameEvent.TURN_END:
            return None
        return [InstantHpLoss(
            source=context.source, target=context.source, amount=self.AMOUNT)]

    def get_effects(self, context):
        return []
