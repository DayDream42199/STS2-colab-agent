from ._status_effect import StatusEffect


class Shrink(StatusEffect):
    """Attacks deal 30% less damage. A negative `amount` is permanent - what
    Shrinker Beetle applies (-1), gone only when the Beetle dies - and a
    positive one lasts that many turns. Weak's heavier cousin; stacks with it.

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

    @property
    def permanent(self):
        return self.amount < 0

    def on_owner_turn_end(self):
        if not self.permanent:
            self.amount -= 1

    def absorb(self, other):
        # Permanent stays permanent (the game's Single stack type for it).
        if self.permanent or other.amount < 0:
            self.amount = -1
        else:
            self.amount += other.amount

    def is_expired(self):
        return self.amount == 0 or not self._applier_alive()
