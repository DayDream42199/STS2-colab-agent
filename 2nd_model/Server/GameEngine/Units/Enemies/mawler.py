from ._scripted import ScriptedEnemy, attack, debuff
from ...Effects.StatusEffects.vulnerable import Vulnerable


class Mawler(ScriptedEnemy):
    """Act 1. Roars first (3 Vulnerable on one player), then alternates Rip
    and Tear (14) with Claw (4 x 2)."""

    DEFAULT_MAX_HP = 72
    DEFAULT_HP_VARIANCE = 0

    ROAR = 3
    RIP_AND_TEAR = 14
    CLAW = 4
    CLAW_HITS = 2

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._opener = debuff("Roar", Vulnerable, self.ROAR)
        self._cycle = (attack("Rip and Tear", self.RIP_AND_TEAR),
                       attack("Claw", self.CLAW, hits=self.CLAW_HITS))

    def pick_move(self, turn):
        if turn == 0:
            return self._opener
        return self._cycle[(turn - 1) % len(self._cycle)]
