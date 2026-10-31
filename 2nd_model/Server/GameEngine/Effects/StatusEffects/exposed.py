from ._status_effect import StatusEffect


class Exposed(StatusEffect):
    """Takes `amount` times the attack damage from everyone EXCEPT whoever
    applied it, until the end of its own turn - the game's KnockdownPower.

    Knockdown's co-op clause: it sets a target up for your teammates. Each
    Knockdown is its own instance in the game, so two players' stack and
    neither multiplies their own attacks: `marks` keeps (applier, amount)."""

    IS_DEBUFF = True
    ATTACKS_ONLY = True
    DAMAGE_ORDER = StatusEffect.MULTIPLICATIVE

    def __init__(self, source, target, amount):
        super().__init__("exposed")
        self.source = source
        self.target = target
        self.amount = amount
        self.marks = [(source, amount)]

    def absorb(self, other):
        self.marks.extend(other.marks)
        self.amount = max(times for _, times in self.marks)

    def modify_incoming_damage(self, amount, attacker=None):
        for applier, times in self.marks:
            if attacker is not None and attacker is not applier:
                amount *= times
        return amount

    def on_owner_turn_end(self):
        # Removed at the end of its owner's turn, whatever the amount.
        self.amount = 0
