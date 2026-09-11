from ._status_effect import StatusEffect


class Cruelty(StatusEffect):
    """Vulnerable enemies take extra damage from us.

    Sits on the attacker but keys off the defender - what `target` is for."""

    BONUS = 0.25
    DAMAGE_ORDER = StatusEffect.MULTIPLICATIVE

    def __init__(self, source, target, amount):
        super().__init__("cruelty")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat

    def modify_outgoing_damage(self, amount, target=None):
        if target is None or not target.get_status("vulnerable"):
            return amount
        return amount * (1 + self.BONUS)
