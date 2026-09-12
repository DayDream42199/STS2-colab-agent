from ._scripted import ScriptedEnemy, attack, buff
from ...Effects.StatusEffects.strength import Strength


class CubexConstruct(ScriptedEnemy):
    """Act 1. Charges Up (+2 Strength), then alternates Repeater Blast (7,
    then +2 more Strength) with Expel Blast (5 x 2). It only gets stronger."""

    NAME = "Cubex Construct"
    DEFAULT_MAX_HP = 65
    DEFAULT_HP_VARIANCE = 0

    CHARGE = 2
    REPEATER = 7
    REPEATER_STRENGTH = 2
    EXPEL = 5
    EXPEL_HITS = 2

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._opener = buff("Charge Up", Strength, self.CHARGE)
        self._cycle = (attack("Repeater Blast", self.REPEATER,
                              gain=(Strength, self.REPEATER_STRENGTH)),
                       attack("Expel Blast", self.EXPEL, hits=self.EXPEL_HITS))

    def pick_move(self, turn):
        if turn == 0:
            return self._opener
        return self._cycle[(turn - 1) % len(self._cycle)]
