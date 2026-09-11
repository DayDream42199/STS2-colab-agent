from ._status_effect import StatusEffect


class StrengthLossThisTurn(StatusEffect):
    """Reduces outgoing damage until the owner's turn ends.

    Its own status rather than a negative StrengthThisTurn, which is_expired
    would cull the moment it landed. `amount` is the size of the penalty."""

    IS_DEBUFF = True

    DAMAGE_ORDER = StatusEffect.ADDITIVE

    def __init__(self, source, target, amount):
        super().__init__("strength_loss_this_turn")
        self.source = source
        self.target = target
        self.amount = amount

    def modify_outgoing_damage(self, amount, target=None):
        return amount - self.amount

    def on_owner_turn_end(self):
        self.amount = 0
