from ._instant_effect import InstantEffect

class InstantDamage(InstantEffect):
    def __init__(self, source, target, amount):
        super().__init__("instant_damage")
        self.source = source
        self.target = target
        self.amount = amount