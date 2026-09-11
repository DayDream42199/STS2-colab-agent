from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_hp_loss import InstantHpLoss


class Choking(StatusEffect):
    """Whenever you play a card this turn, the enemy it was played on loses HP.

    `amount` is the HP lost per card. The first CARD_PLAYED it sees is the
    Choking that applied it - that one does not count."""

    def __init__(self, source, target, amount, victim=None):
        super().__init__("choking")
        self.source = source
        self.target = target
        self.amount = amount
        self.victim = victim
        self.pending = True

    def on_owner_turn_end(self):
        self.amount = 0  # lasts only the turn it was played

    def on_event(self, event, context):
        if event is not GameEvent.CARD_PLAYED:
            return None
        if context.target is not context.source:
            return None
        if self.pending:
            self.pending = False
            return None
        if self.victim is None or not self.victim.is_alive():
            return None
        return [InstantHpLoss(
            source=context.source, target=self.victim, amount=self.amount)]
