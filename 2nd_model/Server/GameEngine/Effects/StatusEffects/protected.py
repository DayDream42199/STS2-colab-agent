from ._status_effect import StatusEffect


class Protected(StatusEffect):
    """Take reduced damage. Handed out by Tank to everyone else."""

    REDUCTION = 0.5
    DAMAGE_ORDER = StatusEffect.MULTIPLICATIVE

    def __init__(self, source, target, amount):
        super().__init__("protected")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass

    def modify_incoming_damage(self, amount, attacker=None):
        return amount * (1 - self.REDUCTION)
