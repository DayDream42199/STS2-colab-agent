from ._scripted import ScriptedEnemy, attack, buff
from ...Effects.StatusEffects.strength import Strength


class Nibbit(ScriptedEnemy):
    """Act 1. Opens with a Butt, then cycles Hesitant Slice (6, and 5 Block
    for itself), Hiss (+2 Strength), Butt (12)."""

    HP_RANGE = (42, 46)

    BUTT = 12
    SLICE = 6
    SLICE_BLOCK = 5
    HISS = 2

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        butt = attack("Butt", self.BUTT)
        self._opener = butt
        self._cycle = (attack("Hesitant Slice", self.SLICE, block=self.SLICE_BLOCK),
                       buff("Hiss", Strength, self.HISS),
                       butt)

    def pick_move(self, turn):
        if turn == 0:
            return self._opener
        return self._cycle[(turn - 1) % len(self._cycle)]
