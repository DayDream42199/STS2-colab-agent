from ._status_effect import StatusEffect


class Shrink(StatusEffect):
    """Attacks deal 30% less damage for `amount` turns (Shrinker Beetle
    applies 3). Weak's heavier cousin, and it stacks with Weak.

    Removed when whoever applied it dies - the reference notes that half of
    the text and does not model it; statuses here know their source, so it is
    modelled: a dead applier's Shrink does nothing and is culled at the next
    tick."""

    IS_DEBUFF = True

    MULTIPLIER = 0.7
    DAMAGE_ORDER = StatusEffect.MULTIPLICATIVE

    def __init__(self, source, target, amount):
        super().__init__("shrink")
        self.source = source
        self.target = target
        self.amount = amount

    def _applier_alive(self):
        return self.source is None or self.source.is_alive()

    def modify_outgoing_damage(self, amount, target=None):
        if not self._applier_alive():
            return amount
        return amount * self.MULTIPLIER

    def is_expired(self):
        return self.amount <= 0 or not self._applier_alive()
