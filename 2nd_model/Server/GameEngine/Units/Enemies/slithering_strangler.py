from ._scripted import ScriptedEnemy, Branch, attack, debuff
from ...Effects.StatusEffects.constrict import Constrict


class SlitheringStrangler(ScriptedEnemy):
    """Act 1. Constrict (3 on every player: 3 damage at the end of each of
    their turns while the Strangler lives) every other turn, so it stacks -
    and in between Thwack (7, and 5 Block) or Lash (12) at random."""

    NAME = "Slithering Strangler"
    HP_RANGE = (53, 55)

    CONSTRICT = 3
    THWACK = 7
    THWACK_BLOCK = 5
    LASH = 12

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._constrict = debuff("Constrict", Constrict, self.CONSTRICT)
        self._branches = (Branch(attack("Thwack", self.THWACK, block=self.THWACK_BLOCK)),
                          Branch(attack("Lash", self.LASH)))

    def pick_move(self, turn):
        return self._constrict if turn % 2 == 0 else self.choose(self._branches)
