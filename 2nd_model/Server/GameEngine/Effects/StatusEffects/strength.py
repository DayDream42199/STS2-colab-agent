from ._status_effect import StatusEffect


class Strength(StatusEffect):
    """Flat bonus to outgoing attack damage. Permanent: unlike most statuses
    it does not tick down at end of turn."""

    DAMAGE_ORDER = StatusEffect.ADDITIVE

    def __init__(self, source, target, amount):
        super().__init__("strength")
        self.source = source
        self.target = target
        self.amount = amount

    @property
    def IS_DEBUFF(self):
        # Below zero it is one, and Artifact stops it - the game's
        # GetTypeForAmount (Soul Siphon's -2).
        return self.amount < 0

    def is_expired(self):
        return self.amount == 0     # below zero it stays (AllowNegative)

    def modify_outgoing_damage(self, amount, target=None):
        return amount + self.amount

    def on_owner_turn_end(self):
        pass
