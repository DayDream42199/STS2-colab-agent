from abc import ABC, abstractmethod

from .._unit import Unit

class Enemy(Unit, ABC):
    DEFAULT_MOVE_POOL = []

    def __init__(self, unit_id, max_hp=None, hp_variance=None, move_pool=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self.move_pool = list(move_pool) if move_pool is not None else list(self.DEFAULT_MOVE_POOL)
        self.intent = None

    @abstractmethod
    def choose_intent(self, context=None):
        pass

    @abstractmethod
    def get_effects(self, context):
        pass

    def to_dict(self):
        data = super().to_dict()
        data.update({"intent": self.intent})
        return data