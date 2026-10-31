from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_play_card import InstantPlayCard


class Mayhem(StatusEffect):
    """At the start of your turn, play the top `amount` cards of your Draw
    Pile (the game's MayhemPower, after the hand is drawn)."""

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
            card_id=card_id, from_pile=InstantPlayCard.DRAW)
            for card_id in reversed(draw[-self.amount:])]
