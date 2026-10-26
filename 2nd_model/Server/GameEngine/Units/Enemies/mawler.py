from ._scripted import ScriptedEnemy, Branch, attack, debuff
from ...Effects.StatusEffects.vulnerable import Vulnerable


class Mawler(ScriptedEnemy):
    """Act 1. Opens with Claw (4 x 2), then picks at random: Rip and Tear (14)
    never twice running, Claw never twice running, and Roar (3 Vulnerable on
    every player) at most once a fight."""

    DEFAULT_MAX_HP = 72
    DEFAULT_HP_VARIANCE = 0

    ROAR = 3
    RIP_AND_TEAR = 14
    CLAW = 4
    CLAW_HITS = 2

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._claw = attack("Claw", self.CLAW, hits=self.CLAW_HITS)
        self._branches = (Branch(attack("Rip and Tear", self.RIP_AND_TEAR), Branch.NO_REPEAT),
                          Branch(debuff("Roar", Vulnerable, self.ROAR), Branch.ONCE),
                          Branch(self._claw, Branch.NO_REPEAT))

    def pick_move(self, turn):
        return self._claw if turn == 0 else self.choose(self._branches)
