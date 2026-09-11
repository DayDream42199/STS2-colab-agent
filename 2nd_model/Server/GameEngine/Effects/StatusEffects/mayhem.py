from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_play_card import InstantPlayCard


class Mayhem(StatusEffect):
    """At the start of your turn, play the top card of your Draw Pile."""

    def __init__(self, source, target, amount):
        super().__init__("mayhem")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat

    def on_event(self, event, context):
        if event is not GameEvent.TURN_START:
            return None
        if context.target is not context.source:
            return None
        draw = context.source.draw_pile
        if not draw:
            return None
        return [InstantPlayCard(
            source=context.source, target=context.source,
            card_id=draw[-1], from_pile=InstantPlayCard.DRAW)]
