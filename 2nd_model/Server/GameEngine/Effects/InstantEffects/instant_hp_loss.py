from ._instant_effect import InstantEffect


class InstantHpLoss(InstantEffect):
    def __init__(self, source, target, amount):
        super().__init__("instant_hp_loss")
        self.source = source
        self.target = target
        self.amount = amount
