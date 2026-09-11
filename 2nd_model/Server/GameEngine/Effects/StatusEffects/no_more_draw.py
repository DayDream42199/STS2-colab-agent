from ._status_effect import StatusEffect


class NoMoreDraw(StatusEffect):
    """You cannot draw any more cards this turn."""

    def __init__(self, source, target, amount):
        super().__init__("no_more_draw")
        self.source = source
        self.target = target
        self.amount = amount

    def modify_cards_drawn(self, amount):
        return 0
