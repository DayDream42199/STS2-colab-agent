from ._scripted import ScriptedEnemy, attack, debuff
from ...Effects.StatusEffects.constrict import Constrict


class SlitheringStrangler(ScriptedEnemy):
    """Act 1. Opens with Constrict (3) on one player - 3 damage at the end of
    each of their turns for as long as the Strangler lives - then alternates
    Thwack (7, and 5 Block for itself) with Lash (12)."""

    NAME = "Slithering Strangler"
    HP_RANGE = (53, 55)

    CONSTRICT = 3
    THWACK = 7
    THWACK_BLOCK = 5
    LASH = 12

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._opener = debuff("Constrict", Constrict, self.CONSTRICT)
        self._cycle = (attack("Thwack", self.THWACK, block=self.THWACK_BLOCK),
                       attack("Lash", self.LASH))

    def pick_move(self, turn):
        if turn == 0:
            return self._opener
        return self._cycle[(turn - 1) % len(self._cycle)]
