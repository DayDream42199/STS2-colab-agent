from ._instant_effect import InstantEffect

class InstantBlock(InstantEffect):
    def __init__(self, source, target, amount):
        super().__init__("instant_block")
        self.source = source
        self.target = target
        self.amount = amount