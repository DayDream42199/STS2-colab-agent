from ._status_effect import StatusEffect


class Ringing(StatusEffect):
    """Ceremonial Beast's Beast Cry: this turn you can play only one card.
    The game afflicts every card with Ringing, and a Ringing card cannot be
    played once you have played one this turn; it is gone at the end of your
    turn. A debuff."""

    IS_DEBUFF = True
    PLAY_CAP = 1

    def __init__(self, source, target, amount=1):
        super().__init__("ringing")
        self.source = source
        self.target = target
        self.amount = amount
