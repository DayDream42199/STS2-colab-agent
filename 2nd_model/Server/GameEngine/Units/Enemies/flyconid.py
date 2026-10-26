from ._scripted import ScriptedEnemy, Branch, attack, debuff
from ...Effects.StatusEffects.vulnerable import Vulnerable
from ...Effects.StatusEffects.frail import Frail


class Flyconid(ScriptedEnemy):
    """Act 1. Three moves picked at random, none twice running: Vulnerable
    Spores (2 Vulnerable on every player, then not for 3 moves), Frail Spores
    (8, and 2 Frail, then not for 2 moves), Smash (11). It never opens with
    Vulnerable Spores - the game's first pick is Frail Spores or Smash."""

    HP_RANGE = (47, 49)

    VULNERABLE = 2
    FRAIL_SPORES = 8
    FRAIL = 2
    SMASH = 11

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        vulnerable = debuff("Vulnerable Spores", Vulnerable, self.VULNERABLE)
        frail = attack("Frail Spores", self.FRAIL_SPORES, inflict=(Frail, self.FRAIL))
        smash = attack("Smash", self.SMASH)
        self._first = (Branch(frail, Branch.NO_REPEAT, cooldown=2),
                       Branch(smash, Branch.NO_REPEAT))
        self._later = (Branch(vulnerable, Branch.NO_REPEAT, cooldown=3),
                       Branch(frail, Branch.NO_REPEAT, cooldown=2),
                       Branch(smash, Branch.NO_REPEAT))

    def pick_move(self, turn):
        return self.choose(self._first if turn == 0 else self._later)
