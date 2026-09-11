from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_add_card import InstantAddCard


class HelloWorld(StatusEffect):
    """At the start of your turn, add a random Common card into your Hand."""

    def on_owner_turn_end(self):
        pass

    def __init__(self, source, target, amount):
        super().__init__("hello_world")
        self.source = source
        self.target = target
        self.amount = amount

    def on_event(self, event, context):
        from ...Registry.card_registry import generatable_card_ids
        from ...Cards._card_enums import CardClass, CardRarity

        if event is not GameEvent.TURN_START:
            return None
        if context.target is not context.source:
            return None
        pool = generatable_card_ids(
            card_class=CardClass.IRONCLAD, rarity=CardRarity.COMMON)
        if not pool:
            return None
        return [InstantAddCard(
            source=context.source, target=context.source,
            card_id=context.rng.choice(pool), pile=InstantAddCard.HAND)]
