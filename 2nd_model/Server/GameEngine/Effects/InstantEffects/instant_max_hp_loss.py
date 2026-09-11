from ._instant_effect import InstantEffect


class InstantMaxHpLoss(InstantEffect):
    """Permanently lower max HP. Current HP follows it down if it would end up
    above the new maximum."""

    def __init__(self, source, target, amount):
        super().__init__("instant_max_hp_loss")
        self.source = source
        self.target = target
        self.amount = amount
