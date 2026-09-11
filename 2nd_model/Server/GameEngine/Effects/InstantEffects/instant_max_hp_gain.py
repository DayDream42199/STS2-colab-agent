from ._instant_effect import InstantEffect


class InstantMaxHpGain(InstantEffect):
    """Raise max HP, and current HP with it - a bigger frame, already filled."""

    def __init__(self, source, target, amount):
        super().__init__("instant_max_hp_gain")
        self.source = source
        self.target = target
        self.amount = amount
