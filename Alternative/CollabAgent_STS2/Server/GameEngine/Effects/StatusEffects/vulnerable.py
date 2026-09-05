from ._status_effect import StatusEffect

class Vulnerable(StatusEffect):
    def __init__(self, source, target, amount):
        super().__init__("vulnerable")
        self.source = source
        self.target = target
        self.amount = amount