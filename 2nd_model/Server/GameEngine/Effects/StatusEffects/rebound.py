from ._status_effect import StatusEffect
from ..InstantEffects.instant_move_card import InstantMoveCard


class Rebound(StatusEffect):
    """The next card you play goes on top of your Draw Pile.

    `pending` skips the first question, which is Rebound's own routing."""

    def __init__(self, source, target, amount):
        super().__init__("rebound")
        self.source = source
        self.target = target
        self.amount = amount
        self.pending = True

    def on_owner_turn_end(self):
        self.amount = 0  # "this turn" only

    def redirect_played_card(self, card, context):
        if self.pending:
            self.pending = False
            return None
        if self.amount <= 0:
            return None
        self.amount -= 1
        return InstantMoveCard.DRAW
