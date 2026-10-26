from ._status_effect import StatusEffect


class NoEnergyGain(StatusEffect):
    """You cannot gain Energy this turn (Expect a Fight). Stops energy gained
    from effects - Bloodletting, Pyre - not the refill at the start of the
    next turn, and is gone by then."""

    IS_DEBUFF = True

    def __init__(self, source, target, amount=1):
        super().__init__("no_energy_gain")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        self.amount = 0

    def modify_energy_gain(self, amount):
        return 0
