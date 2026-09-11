from ._status_effect import StatusEffect


class BlockLockout(StatusEffect):
    """You cannot gain Block for `amount` turns.

    Stops all Block, not just Block from cards: modify_block_gained sees an
    amount, not where it came from."""

    def __init__(self, source, target, amount):
        super().__init__("block_lockout")
        self.source = source
        self.target = target
        self.amount = amount

    def modify_block_gained(self, amount):
        return 0
