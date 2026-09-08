from ._instant_effect import InstantEffect


class InstantHpLoss(InstantEffect):
    """Direct HP loss. Unlike InstantDamage this ignores block entirely and is
    not modified by Strength, Weak or Vulnerable - it is a cost, not an attack."""

    def __init__(self, source, target, amount):
        super().__init__("instant_hp_loss")
        self.source = source
        self.target = target
        self.amount = amount
