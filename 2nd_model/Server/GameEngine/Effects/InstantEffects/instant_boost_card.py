from ._instant_effect import InstantEffect


class InstantBoostCard(InstantEffect):
    """Add damage to specific copies for the rest of the combat.

    Rampage boosts only itself, Maul every copy of Maul: the card picks."""

    def __init__(self, source, target, card_refs, amount):
        super().__init__("instant_boost_card")
        self.source = source
        self.target = target
        self.card_refs = list(card_refs)
        self.amount = amount
