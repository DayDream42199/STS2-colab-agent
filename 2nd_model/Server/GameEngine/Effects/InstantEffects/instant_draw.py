from ._instant_effect import InstantEffect


class InstantDraw(InstantEffect):
    def __init__(self, source, target, amount, rng):
        super().__init__("instant_draw")
        self.source = source
        self.target = target
        self.amount = amount
        self.rng = rng
