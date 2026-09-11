from ._instant_effect import InstantEffect


class InstantHeal(InstantEffect):
    """Restore HP, capped at max. Unit.heal already does the clamping."""

    def __init__(self, source, target, amount):
        super().__init__("instant_heal")
        self.source = source
        self.target = target
        self.amount = amount
