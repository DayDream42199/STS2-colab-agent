from ._status_effect import StatusEffect


class Protected(StatusEffect):
    """Take half damage from attacks. Handed out by Tank to everyone else -
    the game's GuardedPower, which is gone once the tank who gave it is dead."""

    REDUCTION = 0.5
    ATTACKS_ONLY = True
    DAMAGE_ORDER = StatusEffect.MULTIPLICATIVE

    def __init__(self, source, target, amount):
        super().__init__("protected")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass

    def modify_incoming_damage(self, amount, attacker=None):
        if self.source is not None and not self.source.is_alive():
            return amount
        return amount * (1 - self.REDUCTION)

    def is_expired(self):
        return self.source is not None and not self.source.is_alive()
