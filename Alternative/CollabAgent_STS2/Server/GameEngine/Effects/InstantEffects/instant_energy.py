from ._instant_effect import InstantEffect


class InstantEnergy(InstantEffect):
    """Grant energy. Deliberately uncapped: Slay the Spire lets energy exceed
    the per-turn maximum once granted mid-turn."""

    def __init__(self, source, target, amount):
        super().__init__("instant_energy")
        self.source = source
        self.target = target
        self.amount = amount
