from ._status_effect import StatusEffect


class Tank(StatusEffect):
    """Take extra damage yourself. The other half - allies taking less - is a
    separate Protected status the card hands out, because a status can only
    modify damage aimed at the unit carrying it."""

    EXTRA = 0.5
    DAMAGE_ORDER = StatusEffect.MULTIPLICATIVE

    def __init__(self, source, target, amount):
        super().__init__("tank")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat

    def modify_incoming_damage(self, amount, attacker=None):
        return amount * (1 + self.EXTRA)
