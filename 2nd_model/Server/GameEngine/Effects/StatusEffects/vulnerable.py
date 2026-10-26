from ._status_effect import StatusEffect


class Vulnerable(StatusEffect):
    IS_DEBUFF = True
    TICKS_AFTER_ENEMY_TURN = True
    ATTACKS_ONLY = True      # Burn on a Vulnerable player is still 2
    MULTIPLIER = 1.5
    DAMAGE_ORDER = StatusEffect.MULTIPLICATIVE

    def __init__(self, source, target, amount):
        super().__init__("vulnerable")
        self.source = source
        self.target = target
        self.amount = amount

    def modify_incoming_damage(self, amount, attacker=None):
        # The attacker's Cruelty adds to the multiplier: 1.5 + 0.25 = 1.75.
        multiplier = self.MULTIPLIER
        cruelty = attacker.get_status("cruelty") if attacker is not None else None
        if cruelty is not None and attacker is not self.target:
            multiplier += cruelty.amount / 100
        return amount * multiplier
