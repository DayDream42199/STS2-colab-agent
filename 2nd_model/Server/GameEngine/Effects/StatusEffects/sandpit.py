from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_hp_loss import InstantHpLoss


class Sandpit(StatusEffect):
    """In `amount` turns, you are eaten and die.

    Counts down at the start of each of the owner's turns, and kills when it
    reaches 0. It does not decay at end of turn: the only way to push it back
    is Frantic Escape, which adds a turn."""

    IS_DEBUFF = True

    def __init__(self, source, target, amount):
        super().__init__("sandpit")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # ticks at TURN_START, see the class docstring

    def on_event(self, event, context):
        if event is not GameEvent.TURN_START:
            return None
        if context.target is not context.source:
            return None
        self.amount -= 1
        if self.amount > 0:
            return None
        # Being eaten is death, not damage, but losing every HP is the nearest
        # thing the resolver has and gets the player out of the fight.
        ally = context.source
        return [InstantHpLoss(source=ally, target=ally, amount=ally.current_hp)]
