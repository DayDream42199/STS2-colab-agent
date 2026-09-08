from ._status_effect import StatusEffect


class Weak(StatusEffect):
    """The attacker deals less damage. Mirror of Vulnerable, on the other side
    of the exchange."""

    MULTIPLIER = 0.75
    DAMAGE_ORDER = StatusEffect.MULTIPLICATIVE

    def __init__(self, source, target, amount):
        super().__init__("weak")
        self.source = source
        self.target = target
        self.amount = amount

    def modify_outgoing_damage(self, amount):
        return amount * self.MULTIPLIER
