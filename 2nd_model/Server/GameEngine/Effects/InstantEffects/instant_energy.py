from ._instant_effect import InstantEffect


class InstantEnergy(InstantEffect):
    def __init__(self, source, target, amount):
        super().__init__("instant_energy")
        self.source = source
        self.target = target
        self.amount = amount
