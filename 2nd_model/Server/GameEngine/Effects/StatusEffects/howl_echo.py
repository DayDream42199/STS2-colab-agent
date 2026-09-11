from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_play_card import InstantPlayCard


class HowlEcho(StatusEffect):
    """At the end of your turn, if Howl from Beyond is in your Exhaust Pile,
    play it from there.

    Piles hold ids, so this asks whether ANY Howl is exhausted, not this one."""

    CARD_ID = "howl_from_beyond"

    def __init__(self, source, target, amount):
        super().__init__("howl_echo")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass

    def on_event(self, event, context):
        if event is not GameEvent.TURN_END:
            return None
        if context.target is not context.source:
            return None
        if self.CARD_ID not in context.source.exhaust_pile:
            return None
        return [InstantPlayCard(
            source=context.source, target=context.source,
            card_id=self.CARD_ID, from_pile=InstantPlayCard.EXHAUST,
            force_exhaust=True)]
