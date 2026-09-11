from ._instant_effect import InstantEffect


class InstantExhaust(InstantEffect):
    """Exhaust specific cards out of the target's hand.

    The card picks the ids before resolving, so the choice stays with the
    card and the resolver only moves them."""

    def __init__(self, source, target, card_ids):
        super().__init__("instant_exhaust")
        self.source = source
        self.target = target
        self.card_ids = list(card_ids)
