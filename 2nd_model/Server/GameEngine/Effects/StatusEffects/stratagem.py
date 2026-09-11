from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_move_card import InstantMoveCard


class Stratagem(StatusEffect):
    """Whenever your Draw Pile is reshuffled, take a card out of it.

    The question is put once the action that reshuffled has finished, so the
    pile the player picks from is the one they end up with."""

    def __init__(self, source, target, amount):
        super().__init__("stratagem")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # a power, so it lasts the combat

    def on_event(self, event, context):
        if event is not GameEvent.DECK_SHUFFLED:
            return None
        if context.target is not context.source:
            return None
        ally = context.source
        if not ally.draw_pile:
            return None

        def take(chosen):
            return [InstantMoveCard(
                source=ally, target=ally, card_ids=[chosen],
                from_pile=InstantMoveCard.DRAW,
                to_pile=InstantMoveCard.HAND)]

        context.ask(ally, "Take a card from the reshuffled Draw Pile",
                    lambda: list(ally.draw_pile), take)
        return None
