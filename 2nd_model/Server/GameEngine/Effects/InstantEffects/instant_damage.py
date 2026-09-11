from ._instant_effect import InstantEffect

class InstantDamage(InstantEffect):
    """`is_attack=False` is damage that is nobody's attack - a bomb, a boulder.
    It still meets Block, but skips the source's Strength and ATTACKED."""

    def __init__(self, source, target, amount, is_attack=True):
        super().__init__("instant_damage")
        self.source = source
        self.target = target
        self.amount = amount
        self.is_attack = is_attack