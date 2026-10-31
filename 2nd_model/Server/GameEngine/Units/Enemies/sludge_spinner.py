from ._scripted import ScriptedEnemy, Branch, attack
from ...Effects.StatusEffects.strength import Strength
from ...Effects.StatusEffects.weak import Weak


class SludgeSpinner(ScriptedEnemy):
    """Oil Spray (8 and 1 Weak) first, then at random Oil Spray, Slam 11 or
    Rage (6, +3 Strength) - never the same twice running."""

    NAME = "Sludge Spinner"
    HP_RANGE = (37, 39)
    OIL_SPRAY = 8
    SLAM = 11
    RAGE = 6
    RAGE_STRENGTH = 3

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._oil_spray = attack("Oil Spray", self.OIL_SPRAY, inflict=(Weak, 1))
        self._branches = (Branch(self._oil_spray, Branch.NO_REPEAT),
                          Branch(attack("Slam", self.SLAM), Branch.NO_REPEAT),
                          Branch(attack("Rage", self.RAGE, gain=(Strength, self.RAGE_STRENGTH)),
                                 Branch.NO_REPEAT))

    def pick_move(self, turn):
        return self._oil_spray if turn == 0 else self.choose(self._branches)
