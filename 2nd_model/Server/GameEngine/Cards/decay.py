from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Events.game_event import GameEvent
from ..Effects.InstantEffects.instant_damage import InstantDamage


class Decay(Card):
    DAMAGE = 2

    def __init__(self):
        super().__init__(
            card_id = "decay",
            name = "Decay",
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
        return [InstantDamage(
            source=context.source, target=context.source,
            amount=self.DAMAGE, is_attack=False)]

    def get_effects(self, context):
        return []
