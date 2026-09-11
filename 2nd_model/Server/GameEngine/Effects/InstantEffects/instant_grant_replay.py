from ._instant_effect import InstantEffect


class InstantGrantReplay(InstantEffect):
    """Give specific copies extra plays for the rest of the combat.

    Standing, not a charge: a card with Replay 2 resolves three times every
    time it is played, not three times in total."""

    def __init__(self, source, target, card_refs, amount):
        super().__init__("instant_grant_replay")
        self.source = source
        self.target = target
        self.card_refs = list(card_refs)
        self.amount = amount
