from ._status_effect import StatusEffect
from ...Cards._card_enums import CardType


class Tangled(StatusEffect):
    """Attacks cost 1 more energy while this lasts (Vine Shambler's Grasping
    Vines). A duration: one turn per stack, ticking down at end of turn.

    Added before the free-play grants are consulted, so an Attack made free
    by Unrelenting or a this-turn grant still costs nothing - as the
    reference orders it. A printed-0 Attack does cost 1, also as there."""

    IS_DEBUFF = True

    EXTRA = 1

    def __init__(self, source, target, amount):
        super().__init__("tangled")
        self.source = source
        self.target = target
        self.amount = amount

    def modify_card_cost(self, cost, card):
        if card.card_type is CardType.ATTACK:
            return cost + self.EXTRA
        return cost
