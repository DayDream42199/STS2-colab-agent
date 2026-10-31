from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_move_card import InstantMoveCard


class ReturnToHand(StatusEffect):
    """Cards played this turn that come back to hand at the start of the
    owner's next turn (Bolas, Thrumming Hatchet).

    As the game's BeforeHandDraw clause: the card goes to the discard pile
    like any other, and next turn, before the hand is drawn, it is taken from
    whatever pile it is in by then - discard, a reshuffled draw pile, the
    exhaust pile - unless it is already in hand. It holds the refs, since it
    is that copy coming back."""

    PILES = (InstantMoveCard.DISCARD, InstantMoveCard.DRAW, InstantMoveCard.EXHAUST)

    def __init__(self, source, target, card_ref):
        super().__init__("return_to_hand")
        self.source = source
        self.target = target
        self.held = [card_ref]
        self.amount = 1

    def absorb(self, other):
        # Two cards can be waiting at once, so the lists join rather than the
        # amounts adding.
        self.held.extend(other.held)
        self.amount = len(self.held)

    def on_owner_turn_end(self):
        pass  # it lasts until the cards are back, not a number of turns

    def is_expired(self):
        return not self.held

    def on_event(self, event, context):
        if event is not GameEvent.BEFORE_HAND_DRAW:
            return None
        if context.target is not context.source:
            return None
        coming_back, self.held = self.held, []
        self.amount = 0
        ally = context.source
        moves = []
        for ref in coming_back:
            if any(held is ref for held in ally.hand):
                continue
            pile = next((name for name in self.PILES
                         if any(held is ref for held in getattr(ally, name))), None)
            if pile is not None:
                moves.append(InstantMoveCard(
                    source=ally, target=ally, card_ids=[ref],
                    from_pile=pile, to_pile=InstantMoveCard.HAND))
        return moves or None
