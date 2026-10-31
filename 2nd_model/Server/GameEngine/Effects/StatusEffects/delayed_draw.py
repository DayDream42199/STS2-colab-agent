from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_draw import InstantDraw


class DelayedDraw(StatusEffect):
    """Draw `amount` more cards at the start of your next turn - the game's
    DrawCardsNextTurnPower. Two of them add up."""

    def __init__(self, source, target, amount):
        super().__init__("delayed_draw")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # amount is cards, not a duration

    def on_event(self, event, context):
        if event is not GameEvent.TURN_START:
            return None
        if context.target is not context.source or self.amount <= 0:
            return None
        cards, self.amount = self.amount, 0    # spent; the next tick removes it
        return [InstantDraw(source=context.source, target=context.source,
                            amount=cards, rng=context.rngs.shuffle)]
