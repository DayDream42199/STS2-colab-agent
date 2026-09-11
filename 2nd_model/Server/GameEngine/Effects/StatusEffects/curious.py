from ._status_effect import StatusEffect


class Curious(StatusEffect):
    """Powers cost `amount` less. Floors at 0 in Combat.card_cost."""

    def __init__(self, source, target, amount):
        super().__init__("curious")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # a power, so it lasts the combat

    def modify_card_cost(self, cost, card):
        from ...Cards._card_enums import CardType

        return cost - self.amount if card.card_type is CardType.POWER else cost
