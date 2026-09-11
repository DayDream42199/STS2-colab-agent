from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Events.game_event import GameEvent
from ..Effects.InstantEffects.instant_hp_loss import InstantHpLoss


class Regret(Card):
    def __init__(self):
        super().__init__(
            card_id = "regret",
            name = "Regret",
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
        # One HP per card still held, this card included.
        held = len(context.source.hand)
        if held <= 0:
            return None
        return [InstantHpLoss(
            source=context.source, target=context.source, amount=held)]

    def get_effects(self, context):
        return []
