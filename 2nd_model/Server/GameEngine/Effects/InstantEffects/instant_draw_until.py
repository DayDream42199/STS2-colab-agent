from ._instant_effect import InstantEffect


class InstantDrawUntil(InstantEffect):
    """Keep drawing while the cards coming up are `while_type`.

    The card that stops it is kept: Pillage draws through to a non-Attack."""

    def __init__(self, source, target, while_type, rng=None):
        super().__init__("instant_draw_until")
        self.source = source
        self.target = target
        self.while_type = while_type
        self.rng = rng
