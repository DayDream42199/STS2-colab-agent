from ._scripted import ScriptedEnemy, attack, buff
from ...Effects.StatusEffects.strength import Strength


class FuzzyWurmCrawler(ScriptedEnemy):
    """Act 1. A weak spit that gets much less weak: Acid Goop (4), Inhale
    (+7 Strength), Acid Goop, repeating."""

    NAME = "Fuzzy Wurm Crawler"
    HP_RANGE = (55, 57)

    GOOP = 4
    INHALE = 7

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        goop = attack("Acid Goop", self.GOOP)
        self._cycle = (goop, buff("Inhale", Strength, self.INHALE), goop)

    def pick_move(self, turn):
        return self._cycle[turn % len(self._cycle)]
