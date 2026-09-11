from ._status_effect import StatusEffect


class StrengthThisTurn(StatusEffect):
    """Strength that lasts only until the owner's turn ends. Kept separate
    from Strength so the two stack independently and expire differently."""

    DAMAGE_ORDER = StatusEffect.ADDITIVE

    def __init__(self, source, target, amount):
        super().__init__("strength_this_turn")
        self.source = source
        self.target = target
        self.amount = amount

    def modify_outgoing_damage(self, amount, target=None):
        return amount + self.amount

    def on_owner_turn_end(self):
        # All of it goes at once, rather than ticking down by 1.
        self.amount = 0
