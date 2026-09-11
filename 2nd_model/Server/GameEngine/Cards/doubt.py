from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Events.game_event import GameEvent
from ..Effects.StatusEffects.weak import Weak


class Doubt(Card):
    WEAK = 1

    def __init__(self):
        super().__init__(
            card_id = "doubt",
            name = "Doubt",
            card_type = CardType.CURSE,
            card_class = CardClass.CURSE,
            rarity = CardRarity.COMMON,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(playable=False)
        )

    def on_event(self, event, context):
        if event is not GameEvent.TURN_END:
            return None
        return [Weak(
            source=context.source, target=context.source, amount=self.WEAK)]

    def get_effects(self, context):
        return []
