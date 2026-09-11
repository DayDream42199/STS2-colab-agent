from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_move_card import InstantMoveCard


class ReturnToHand(StatusEffect):
    """Cards held out of play until the owner's next turn, then put in hand.

    It holds the refs itself, because a card waiting to come back is in no
    pile - and holding the ref is what makes it the same card coming back."""

    # Asked before Nostalgia and Rebound: this one is claiming its own card.
    REDIRECT_ORDER = 0

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

    def redirect_played_card(self, card, context):
        if any(held is card.ref for held in self.held):
            return InstantMoveCard.GONE
        return None

    def on_event(self, event, context):
        if event is not GameEvent.TURN_START:
            return None
        if context.target is not context.source:
            return None
        coming_back, self.held = self.held, []
        self.amount = 0
        if not coming_back:
            return None
        return [InstantMoveCard(
            source=context.source, target=context.source,
            card_ids=coming_back,
            from_pile=InstantMoveCard.GONE,
            to_pile=InstantMoveCard.HAND)]
