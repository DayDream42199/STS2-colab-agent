from abc import ABC

from .._unit import Unit

class Ally(Unit, ABC):
    DEFAULT_MAX_ENERGY = 3
    DEFAULT_DECK = []

    def __init__(self, unit_id, max_hp=None, hp_variance=None, max_energy=None, deck=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)

        self.max_energy = max_energy if max_energy is not None else self.DEFAULT_MAX_ENERGY
        self.energy = self.max_energy

        self.deck = list(deck) if deck is not None else list(self.DEFAULT_DECK)
        self.draw_pile = []
        self.hand = []
        self.discard_pile = []

    def start_turn(self):
        self.clear_block()
        self.energy = self.max_energy

    def spend_energy(self, amount):
        if amount > self.energy:
            raise ValueError("Not enough energy.")
        self.energy -= amount

    def to_dict(self):
        data = super().to_dict()
        data.update({
            "energy": self.energy,
            "max_energy": self.max_energy,
            "hand": list(self.hand),
        })
        return data