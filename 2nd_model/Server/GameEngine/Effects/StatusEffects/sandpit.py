from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_hp_loss import InstantHpLoss


class Sandpit(StatusEffect):
    """In `amount` turns, you are eaten and die.

    Counts down at the start of each enemy turn, as the game's SandpitPower
    does (AfterSideTurnStartLate, enemy side) - so the player gets their whole
    turn to dig for Frantic Escapes before it bites. Kills when it reaches 0.
    It does not decay at end of turn: the only way to push it back is
    Frantic Escape, which adds a turn."""

    IS_DEBUFF = True

    def __init__(self, source, target, amount):
        super().__init__("sandpit")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # ticks at TURN_START, see the class docstring

    def on_event(self, event, context):
        if event is not GameEvent.ENEMY_TURN_START:
            return None
        if self.source is not None and not self.source.is_alive():
            return None          # the pit goes with the boss
        self.amount -= 1
        if self.amount > 0:
            return None
        # Being eaten is death, not damage, but losing every HP is the nearest
        # thing the resolver has and gets the player out of the fight.
        ally = context.source
        return [InstantHpLoss(source=ally, target=ally, amount=ally.current_hp)]
