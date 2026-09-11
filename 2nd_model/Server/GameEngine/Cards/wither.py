from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Events.game_event import GameEvent
from ..Effects.InstantEffects.instant_damage import InstantDamage


class Wither(Card):
    AMOUNT = 3

    def __init__(self):
        super().__init__(
            card_id = "wither",
            name = "Wither",
            card_type = CardType.STATUS,
            card_class = CardClass.STATUS,
            rarity = CardRarity.COMMON,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(playable=False)
        )

    def on_event(self, event, context):
        # Only while it is still sitting in hand at end of turn. Aeonglass
        # hands out Wither+1, Wither+2... as it intensifies: that is a copy
        # carrying bonus_damage, so it reads as 3+X here with nothing else.
        if event is not GameEvent.TURN_END:
            return None
        return [InstantDamage(
            source=context.source, target=context.source,
            amount=self.AMOUNT + self.bonus_damage, is_attack=False)]

    def get_effects(self, context):
        return []
