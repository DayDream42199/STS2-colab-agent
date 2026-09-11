from ._instant_effect import InstantEffect


class InstantMoveCard(InstantEffect):
    """Move specific cards between a unit's piles.

    `to_top` matters only for the draw pile, drawn from the end."""

    DRAW = "draw_pile"
    DISCARD = "discard_pile"
    HAND = "hand"
    EXHAUST = "exhaust_pile"
    # Leaves play without landing anywhere - a transform. Not EXHAUST, which
    # would give every "whenever you exhaust" power a trigger it should not get.
    GONE = "gone"

    def __init__(self, source, target, card_ids, from_pile, to_pile, to_top=True):
        super().__init__("instant_move_card")
        self.source = source
        self.target = target
        self.card_ids = list(card_ids)
        self.from_pile = from_pile
        self.to_pile = to_pile
        self.to_top = to_top
