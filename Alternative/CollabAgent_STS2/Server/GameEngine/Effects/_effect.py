from abc import ABC

class Effect(ABC):
    def __init__(self, effect_id):
        self.effect_id = effect_id