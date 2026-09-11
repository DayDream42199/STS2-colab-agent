from ._status_effect import StatusEffect
from ..InstantEffects.instant_move_card import InstantMoveCard


class Nostalgia(StatusEffect):
    """The first Attack or Skill you play each turn goes on top of your Draw
    Pile instead of to the discard."""

    COUNTER = "nostalgia_used"

    def __init__(self, source, target, amount):
        super().__init__("nostalgia")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass

    def redirect_played_card(self, card, context):
        from ...Cards._card_enums import CardType

        if card.card_type not in (CardType.ATTACK, CardType.SKILL):
            return None
        owner = context.source
        if owner.turn_count(self.COUNTER):
            return None
        owner.turn_counters[self.COUNTER] = 1
        return InstantMoveCard.DRAW
