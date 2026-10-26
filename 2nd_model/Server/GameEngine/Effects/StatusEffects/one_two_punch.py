from ._status_effect import StatusEffect


class OneTwoPunch(StatusEffect):
    """This turn, your next `amount` Attacks are played an extra time. Gone at
    the end of the turn whether or not it was used. Combat._extra_plays spends
    the charges."""

    def __init__(self, source, target, amount):
        super().__init__("one_two_punch")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        self.amount = 0          # removed by the tick that calls this
