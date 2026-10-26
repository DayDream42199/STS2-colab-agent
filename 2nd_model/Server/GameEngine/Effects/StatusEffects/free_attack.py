from ._status_effect import StatusEffect
from ...Cards._card_enums import CardType


class FreeAttack(StatusEffect):
    """Your next `amount` Attacks cost 0 (Unrelenting). No deadline: it waits
    for the next Attack whenever that is.

    Priced last (COST_ORDER), so Tangled's +1 does not survive it. A charge is
    spent on every Attack played - from hand or auto-played, and even one
    that already cost 0 - which is what the game's FreeAttackPower does;
    Combat._spend_on_play does the spending."""

    COST_ORDER = 100

    def __init__(self, source, target, amount):
        super().__init__("free_attack")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass

    def modify_card_cost(self, cost, card):
        if self.amount > 0 and card.card_type is CardType.ATTACK:
            return 0
        return cost
