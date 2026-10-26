from ._status_effect import StatusEffect


class Cruelty(StatusEffect):
    """Your attacks on a Vulnerable enemy count Vulnerable as `amount` percent
    stronger: 1.5x becomes 1.75x with one Cruelty, 2x upgraded, and copies add
    up (the game's CrueltyPower is a counter).

    Only the holder's attacks - the game's Vulnerable reads Cruelty off the
    attacker (dealer.GetPower<CrueltyPower>), not off the whole party. And it
    is added to the multiplier, not multiplied after it. So this status only
    carries the number; Vulnerable does the arithmetic."""

    def __init__(self, source, target, amount):
        super().__init__("cruelty")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat
