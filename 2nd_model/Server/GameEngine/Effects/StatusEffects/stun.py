from ._status_effect import StatusEffect


class Stun(StatusEffect):
    """Skip the owner's next `amount` turns.

    Counted down by Combat when it skips a turn, not on the status tick."""

    IS_DEBUFF = True

    def __init__(self, source, target, amount):
        super().__init__("stun")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # spent by being skipped, not by time passing
