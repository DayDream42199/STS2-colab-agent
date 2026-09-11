from ._status_effect import StatusEffect


class Enlightenment(StatusEffect):
    """Cards cost at most 1. A cap, so Corruption's 0 for Skills survives it."""

    CAP = 1

    def __init__(self, source, target, amount):
        super().__init__("enlightenment")
        self.source = source
        self.target = target
        self.amount = amount

    def modify_card_cost(self, cost, card):
        return min(cost, self.CAP)
