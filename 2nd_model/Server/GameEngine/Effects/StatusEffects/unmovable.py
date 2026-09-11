from ._status_effect import StatusEffect


class Unmovable(StatusEffect):
    """The first Block gained each turn is doubled."""

    def __init__(self, source, target, amount):
        super().__init__("unmovable")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat

    def modify_block_gained(self, amount):
        if self.target is None or self.target.turn_count("block_gained") > 0:
            return amount
        return amount * 2
