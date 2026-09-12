from ._instant_effect import InstantEffect


class InstantAddCard(InstantEffect):
    """Put copies of a card into one of the target's piles - how Wound and Burn
    ever reach a deck."""

    DRAW = "draw_pile"
    DISCARD = "discard_pile"
    HAND = "hand"

    def __init__(self, source, target, card_id, pile=DISCARD, amount=1, rng=None,
                 bottom=False):
        super().__init__("instant_add_card")
        self.source = source
        self.target = target
        self.card_id = card_id
        self.pile = pile
        self.amount = amount
        self.rng = rng
        # Draw pile only: under everything, drawn last. Otherwise on top with
        # no rng, or at random depths with one.
        self.bottom = bottom
