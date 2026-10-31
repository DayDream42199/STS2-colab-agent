from ._instant_effect import InstantEffect


class InstantCapCost(InstantEffect):
    """Make specific copies cost at most `amount`: this turn or until each is
    next played, or with `this_combat` for the rest of the combat.

    Enlightenment caps the cards in hand at 1 (Enlightenment+ for the combat)."""

    def __init__(self, source, target, card_refs, amount, this_combat=False):
        super().__init__("instant_cap_cost")
        self.source = source
        self.target = target
        self.card_refs = list(card_refs)
        self.amount = amount
        self.this_combat = this_combat
