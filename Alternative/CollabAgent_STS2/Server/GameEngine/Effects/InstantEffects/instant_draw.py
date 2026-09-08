from ._instant_effect import InstantEffect


class InstantDraw(InstantEffect):
    """Draw cards into the target's hand. Carries the rng because drawing may
    reshuffle the discard pile, and the resolver has no combat reference."""

    def __init__(self, source, target, amount, rng):
        super().__init__("instant_draw")
        self.source = source
        self.target = target
        self.amount = amount
        self.rng = rng
