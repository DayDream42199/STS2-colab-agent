from ._status_effect import StatusEffect


class Frail(StatusEffect):
    IS_DEBUFF = True
    MULTIPLIER = 0.75
    DAMAGE_ORDER = StatusEffect.MULTIPLICATIVE

    def __init__(self, source, target, amount):
        super().__init__("frail")
        self.source = source
        self.target = target
        self.amount = amount

    def modify_block_gained(self, amount):
        return amount * self.MULTIPLIER
