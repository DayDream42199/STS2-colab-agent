from ._status_effect import StatusEffect


class Dexterity(StatusEffect):
    """Flat bonus to Block gained. The Block counterpart of Strength, and
    permanent for the same reason."""

    def __init__(self, source, target, amount):
        super().__init__("dexterity")
        self.source = source
        self.target = target
        self.amount = amount

    def modify_block_gained(self, amount):
        return amount + self.amount

    def on_owner_turn_end(self):
        pass
