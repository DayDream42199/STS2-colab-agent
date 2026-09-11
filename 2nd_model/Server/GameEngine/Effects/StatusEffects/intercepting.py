from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent


class Intercepting(StatusEffect):
    """Attacks aimed at your teammates hit you instead.

    Clears on the owner's next TURN_START, not the end-of-turn tick, which runs
    before the enemy phase - it would be gone before anything attacked.

    It covers every other living ally rather than a list snapshotted when it
    was played: the roster is fixed for a combat, so the two are the same."""

    def __init__(self, source, target, amount):
        super().__init__("intercepting")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # survives into the enemy phase; see the class docstring

    def on_event(self, event, context):
        if event is GameEvent.TURN_START and context.target is context.source:
            self.amount = 0  # spent; the next tick removes it
        return None
