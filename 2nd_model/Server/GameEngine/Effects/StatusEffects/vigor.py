from ._status_effect import StatusEffect


class Vigor(StatusEffect):
    """Adds to the damage of the next attack, then is spent.

    Spent by the first hit that lands, so a multi-hit attack gets it once.
    Reading the bonus spends nothing - an intent or Thrash may ask."""

    DAMAGE_ORDER = StatusEffect.ADDITIVE

    def __init__(self, source, target, amount):
        super().__init__("vigor")
        self.source = source
        self.target = target
        self.amount = amount

    def modify_outgoing_damage(self, amount, target=None):
        if self.amount <= 0:
            return amount
        return amount + self.amount

    def after_attack_dealt(self):
        self.amount = 0  # spent; the next tick removes it

    def on_owner_turn_end(self):
        pass
