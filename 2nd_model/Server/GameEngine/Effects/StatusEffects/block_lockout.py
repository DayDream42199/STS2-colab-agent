from ._status_effect import StatusEffect


class BlockLockout(StatusEffect):
    """You cannot gain Block from cards for `amount` turns.

    Only a card's own Block, as the game's NoBlockPower (not Unpowered, and
    from a card): Entrench's doubling, a power's Block (Plating, Prolong) and
    a teammate's Beacon of Hope still land."""

    BLOCK_POWERED_ONLY = True

    def __init__(self, source, target, amount):
        super().__init__("block_lockout")
        self.source = source
        self.target = target
        self.amount = amount

    def modify_block_gained(self, amount):
        return 0
