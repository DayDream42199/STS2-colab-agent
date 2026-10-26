from ._instant_effect import InstantEffect


class InstantPlayCard(InstantEffect):
    """Play a card the player did not choose.

    Combat resolves this one, not Resolver, which knows nothing about turns
    or targeting. `at` None means auto-target.

    `card_id` None means "the top `count` cards of the draw pile", whatever
    they are by the time this resolves - Havoc and Cascade. Chosen then, not
    when the card is played, so the discard can be shuffled in first."""

    DRAW = "draw_pile"
    DISCARD = "discard_pile"
    HAND = "hand"
    EXHAUST = "exhaust_pile"

    def __init__(self, source, target, card_id, from_pile=None, at=None,
                 force_exhaust=False, count=1):
        super().__init__("instant_play_card")
        self.source = source
        self.target = target
        self.card_id = card_id
        self.from_pile = from_pile
        self.at = at
        self.force_exhaust = force_exhaust
        self.count = count
