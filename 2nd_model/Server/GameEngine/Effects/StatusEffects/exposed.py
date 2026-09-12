from ._status_effect import StatusEffect


class Exposed(StatusEffect):
    """Takes double damage from everyone EXCEPT whoever applied it.

    Knockdown's co-op clause: it sets a target up for your teammates."""

    IS_DEBUFF = True
    ATTACKS_ONLY = True

    MULTIPLIER = 2.0
    DAMAGE_ORDER = StatusEffect.MULTIPLICATIVE

    def __init__(self, source, target, amount):
        super().__init__("exposed")
        self.source = source
        self.target = target
        self.amount = amount

    def modify_incoming_damage(self, amount, attacker=None):
        if attacker is None or attacker is self.source:
            return amount
        return amount * self.MULTIPLIER
