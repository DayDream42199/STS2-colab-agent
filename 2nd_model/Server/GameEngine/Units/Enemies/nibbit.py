from ._scripted import ScriptedEnemy, attack, buff
from ...Effects.StatusEffects.strength import Strength


class Nibbit(ScriptedEnemy):
    """Act 1. Butt (12), Hesitant Slice (6, and 5 Block), Hiss (+2 Strength),
    round and round. Where it starts depends on the encounter, as in the
    game: alone it Butts first; in a pair the front one Slices first and the
    back one Hisses first."""

    HP_RANGE = (42, 46)

    BUTT = 12
    SLICE = 6
    SLICE_BLOCK = 5
    HISS = 2

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._cycle = (attack("Butt", self.BUTT),
                       attack("Hesitant Slice", self.SLICE, block=self.SLICE_BLOCK),
                       buff("Hiss", Strength, self.HISS))
        self._start = None

    def pick_move(self, turn):
        if self._start is None:
            nibbits = [e for e in self.context.all_enemies if type(e) is Nibbit] \
                if self.context is not None else [self]
            if len(nibbits) <= 1:
                self._start = 0                                    # alone: Butt
            else:
                self._start = 1 if self.same_kind_index(self.context) == 0 else 2
        return self._cycle[(self._start + turn) % len(self._cycle)]
