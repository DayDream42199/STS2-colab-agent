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
        # The range max HP is rolled from, and whether that is still to do:
        # built with no rng, an enemy rolls as it enters a fight instead
        # (Combat._roll_hp), as the game rolls a monster's HP only then.
        self.hp_range = (base_hp - variance, base_hp + variance) if variance > 0 else None
        self.hp_unrolled = self.hp_range is not None and rng is None

        self.block = 0
        self.statuses = {}
        # Reset by Combat at the start of each player turn. Fed from the
        # events Combat already emits, so cards can ask things like
        # "did I lose HP this turn" without their own bookkeeping.
        self.turn_counters = {}
        # This turn's Block gains from a card or a move, as the card play
        # each came from (None for a move) - the game's BlockGainedEntry,
        # which Unmovable counts.
        self.card_blocks = []
        # Same idea, never reset: "this combat" rather than "this turn".
        self.combat_counters = {}

    @staticmethod
    def _roll_max_hp(base_max_hp, hp_variance, rng=None):
        # No rng, no roll: the base number, rather than a draw from Python's
        # unseeded global random that no seed could reproduce.
        if hp_variance <= 0 or rng is None:
            return base_max_hp
        return rng.randint(base_max_hp - hp_variance, base_max_hp + hp_variance)

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
        remaining = self._hp_lost(amount - absorbed)
        self.current_hp = max(0, self.current_hp - remaining)
        return remaining

    def lose_hp(self, amount):
        if amount <= 0:
            return 0
        amount = self._hp_lost(amount)
        self.current_hp = max(0, self.current_hp - amount)
        return amount

    def _hp_lost(self, amount):
        """What is lost of `amount`, once Block has had its share - the game's
        ModifyHpLostAfterOsty (Slippery). Only a real hit or loss comes here,
        never a preview, so a status may spend a charge on it."""
        for status in list(self.statuses.values()):
            amount = status.modify_hp_lost(amount)
        return amount

    def add_block(self, amount):
        if amount > 0:
            self.block += amount

    def clear_block(self):
        # Barricade and its kind. Checked in the one place block is cleared, so
        # it holds for the ally turn start and the enemy turn start alike.
        if any(status.keeps_block() for status in self.statuses.values()):
            return
        self.block = 0

    def heal(self, amount):
        if amount > 0:
            self.current_hp = min(self.max_hp, self.current_hp + amount)

    def turn_count(self, key):
        return self.turn_counters.get(key, 0)

    def combat_count(self, key):
        return self.combat_counters.get(key, 0)

    def reset_turn_counters(self):
        self.turn_counters = {}
        self.card_blocks = []

    def get_status(self, effect_id):
        return self.statuses.get(effect_id)

    def apply_status(self, status_effect):
        existing = self.statuses.get(status_effect.effect_id)
        if existing is not None:
            existing.absorb(status_effect)
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