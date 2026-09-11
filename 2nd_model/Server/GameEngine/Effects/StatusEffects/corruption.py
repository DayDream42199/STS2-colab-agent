from ._status_effect import StatusEffect
from ..InstantEffects.instant_move_card import InstantMoveCard


class Corruption(StatusEffect):
    """Skills cost 0, and every Skill you play is Exhausted."""

    def __init__(self, source, target, amount):
        super().__init__("corruption")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat

    def modify_card_cost(self, cost, card):
        from ...Cards._card_enums import CardType

        return 0 if card.card_type is CardType.SKILL else cost

    def redirect_played_card(self, card, context):
        from ...Cards._card_enums import CardType

        if card.card_type is not CardType.SKILL:
            return None
        return InstantMoveCard.EXHAUST
