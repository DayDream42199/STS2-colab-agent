from ._scripted import ScriptedEnemy, Branch, attack
from ...Effects.StatusEffects.frail import Frail
from ...Effects.StatusEffects.suck import Suck


class FossilStalker(ScriptedEnemy):
    """Underdocks. Latch 12 first, then at random Latch, Tackle 9 (+1 Frail)
    or Lash 3 x 2 - none more than twice running. Suck 3: after each attack,
    3 Strength for every hit that got through Block."""

    NAME = "Fossil Stalker"
    HP_RANGE = (51, 53)
    SUCK = 3
    TACKLE = 9
    LATCH = 12
    LASH = 3
    LASH_HITS = 2

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._latch = attack("Latch", self.LATCH)
        self._branches = (Branch(self._latch, 2),
                          Branch(attack("Tackle", self.TACKLE, inflict=(Frail, 1)), 2),
                          Branch(attack("Lash", self.LASH, hits=self.LASH_HITS), 2))

    def on_combat_start(self, context):
        return [Suck(source=self, target=self, amount=self.SUCK)]

    def pick_move(self, turn):
        return self._latch if turn == 0 else self.choose(self._branches)
