from ._status_effect import StatusEffect


class Vulnerable(StatusEffect):
    IS_DEBUFF = True
    MULTIPLIER = 1.5
    DAMAGE_ORDER = StatusEffect.MULTIPLICATIVE

    def __init__(self, source, target, amount):
        super().__init__("vulnerable")
        self.source = source
        self.target = target
        self.amount = amount

    def modify_incoming_damage(self, amount, attacker=None):
        return amount * self.MULTIPLIER
