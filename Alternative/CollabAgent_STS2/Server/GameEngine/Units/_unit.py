import random
from abc import ABC

class Unit(ABC):
    DEFAULT_MAX_HP = 1
    DEFAULT_HP_VARIANCE = 0

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        self.unit_id = unit_id
        self.name = type(self).__name__

        base_hp = max_hp if max_hp is not None else self.DEFAULT_MAX_HP
        variance = hp_variance if hp_variance is not None else self.DEFAULT_HP_VARIANCE
        self.max_hp = self._roll_max_hp(base_hp, variance, rng)
        self.current_hp = self.max_hp

        self.block = 0
        self.statuses = {}

    @staticmethod
    def _roll_max_hp(base_max_hp, hp_variance, rng=None):
        if hp_variance <= 0:
            return base_max_hp
        source = rng if rng is not None else random
        return source.randint(base_max_hp - hp_variance, base_max_hp + hp_variance)

    @classmethod
    def type_id(cls):
        return cls.__name__.lower()

    def is_alive(self):
        return self.current_hp > 0

    def take_damage(self, amount):
        if amount <= 0:
            return 0
        absorbed = min(self.block, amount)
        self.block -= absorbed
        remaining = amount - absorbed
        self.current_hp = max(0, self.current_hp - remaining)
        return remaining

    def add_block(self, amount):
        if amount > 0:
            self.block += amount

    def clear_block(self):
        self.block = 0

    def heal(self, amount):
        if amount > 0:
            self.current_hp = min(self.max_hp, self.current_hp + amount)

    def get_status(self, effect_id):
        return self.statuses.get(effect_id)

    def apply_status(self, status_effect):
        existing = self.statuses.get(status_effect.effect_id)
        if existing is not None:
            existing.amount += status_effect.amount
        else:
            self.statuses[status_effect.effect_id] = status_effect

    def remove_status(self, effect_id):
        self.statuses.pop(effect_id, None)

    def to_dict(self):
        return {
            "unit_id": self.unit_id,
            "type_id": self.type_id(),
            "name": self.name,
            "max_hp": self.max_hp,
            "current_hp": self.current_hp,
            "block": self.block,
            "statuses": {eid: e.amount for eid, e in self.statuses.items()},
        }