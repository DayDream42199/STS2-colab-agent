from ._status_effect import StatusEffect


class Vigor(StatusEffect):
    """Adds to the damage of the next attack, then is spent.

    Spent in modify_outgoing_damage, so a multi-hit attack gets it once."""

    DAMAGE_ORDER = StatusEffect.ADDITIVE

    def __init__(self, source, target, amount):
        super().__init__("vigor")
        self.source = source
        self.target = target
        self.amount = amount

    def modify_outgoing_damage(self, amount, target=None):
        if self.amount <= 0:
            return amount
        bonus = self.amount
        self.amount = 0  # spent; the next tick removes it
        return amount + bonus

    def on_owner_turn_end(self):
        pass
