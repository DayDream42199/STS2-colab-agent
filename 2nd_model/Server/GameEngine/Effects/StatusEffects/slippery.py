from ._status_effect import StatusEffect


class Slippery(StatusEffect):
    """Each hit or loss that gets through Block takes 1 HP, however big, and
    spends a charge. Charges, not a duration (Inklet arrives with 1). The
    game's SlipperyPower; in co-op the game multiplies it by the player count.
    """

    def __init__(self, source, target, amount):
        super().__init__("slippery")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # charges, not a duration

    def modify_hp_lost(self, amount):
        if self.amount <= 0 or amount < 1:
            return amount
        self.amount -= 1
        return 1


def slippery_for(players, amount):
    """The game's co-op scaling for Slippery: times the player count."""
    return amount * max(1, players)
