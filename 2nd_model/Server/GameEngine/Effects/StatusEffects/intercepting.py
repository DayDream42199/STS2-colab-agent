from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent


class Intercepting(StatusEffect):
    """Attacks aimed at the players you cover hit you instead.

    Clears on the owner's next TURN_START, not the end-of-turn tick, which runs
    before the enemy phase - it would be gone before anything attacked.

    Only the player each Intercept was played on is covered, as the game's
    CoveredPower is applied to the target alone; two Intercepts on two
    teammates cover both."""

    def __init__(self, source, target, amount, covered=None):
        super().__init__("intercepting")
        self.source = source
        self.target = target
        self.amount = amount
        self.covered = [covered] if covered is not None else []

    def absorb(self, other):
        self.amount = max(self.amount, other.amount)
        self.covered += [unit for unit in other.covered if unit not in self.covered]

    def on_owner_turn_end(self):
        pass  # survives into the enemy phase; see the class docstring

    def on_event(self, event, context):
        if event is GameEvent.TURN_START and context.target is context.source:
            self.amount = 0  # spent; the next tick removes it
        return None
