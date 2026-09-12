from ._scripted import ScriptedEnemy, attack, debuff
from ...Effects.StatusEffects.vulnerable import Vulnerable
from ...Effects.StatusEffects.frail import Frail


class Flyconid(ScriptedEnemy):
    """Act 1. Opens with Weakening Spores (2 Vulnerable on one player), then
    alternates Frail Spores (8, and 2 Frail) with Smash (11)."""

    HP_RANGE = (47, 49)

    VULNERABLE = 2
    FRAIL_SPORES = 8
    FRAIL = 2
    SMASH = 11

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._opener = debuff("Weakening Spores", Vulnerable, self.VULNERABLE)
        self._cycle = (attack("Frail Spores", self.FRAIL_SPORES, inflict=(Frail, self.FRAIL)),
                       attack("Smash", self.SMASH))

    def pick_move(self, turn):
        if turn == 0:
            return self._opener
        return self._cycle[(turn - 1) % len(self._cycle)]
