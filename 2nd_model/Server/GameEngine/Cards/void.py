from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Events.game_event import GameEvent
from ..Effects.InstantEffects.instant_energy import InstantEnergy


class Void(Card):
    """Unplayable. Ethereal. Whenever you draw this card, lose 1 Energy."""

    ENERGY = -1

    def __init__(self):
        super().__init__(
            card_id = "void",
            name = "Void",
            card_type = CardType.STATUS,
            card_class = CardClass.STATUS,
            rarity = CardRarity.COMMON,
            cost = 0,
            target_type = TargetType.SELF,
            properties = CardProperties(playable=False, ethereal=True)
        )

    def get_effects(self, context):
        return []

    def on_event(self, event, context):
        # Combat sends CARD_DRAWN to the cards that were drawn, one dispatch
        # each, so this fires once per copy drawn and not once per copy held.
        if event is not GameEvent.CARD_DRAWN:
            return None
        return [InstantEnergy(
            source=context.source, target=context.source, amount=self.ENERGY)]
