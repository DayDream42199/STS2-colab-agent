from ._instant_effect import InstantEffect


class InstantRaiseCost(InstantEffect):
    """Make specific copies cost more for the rest of the combat.

    Frantic Escape raises its own price every time it is played."""

    def __init__(self, source, target, card_refs, amount):
        super().__init__("instant_raise_cost")
        self.source = source
        self.target = target
        self.card_refs = list(card_refs)
        self.amount = amount
