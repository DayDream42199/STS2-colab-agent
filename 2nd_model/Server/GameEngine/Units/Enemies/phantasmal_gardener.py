from ._scripted import ScriptedEnemy, attack, buff
from ...Effects.StatusEffects.skittish import Skittish, skittish_for
from ...Effects.StatusEffects.strength import Strength


class PhantasmalGardener(ScriptedEnemy):
    """Underdocks elite, four of them (PhantasmalGardenersElite). Bite 5,
    Lash 7, Flail 1 x 3, Enlarge +2 Strength, round and round - the first
    opens with Flail, the second Bite, the third Lash, the fourth Enlarge.
    Skittish 6: the first card attack each turn that gets through its Block
    leaves it 6 Block (half again per extra player)."""

    NAME = "Phantasmal Gardener"
    CATEGORY = "elite"
    HP_RANGE = (26, 31)
    SKITTISH = 6
    BITE = 5
    LASH = 7
    FLAIL = 1
    FLAIL_HITS = 3
    ENLARGE_STRENGTH = 2
    # Each slot's opening move, as an index into the cycle (the game's INIT_MOVE).
    OPENING = (2, 0, 1, 3)

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._cycle = (attack("Bite", self.BITE),
                       attack("Lash", self.LASH),
                       attack("Flail", self.FLAIL, hits=self.FLAIL_HITS),
                       buff("Enlarge", Strength, self.ENLARGE_STRENGTH))
        self._start = 0

    def on_combat_start(self, context):
        return [Skittish(source=self, target=self,
                         amount=skittish_for(len(context.all_allies), self.SKITTISH))]

    def pick_move(self, turn):
        if turn == 0:
            slot = self.same_kind_index(self.context)
            self._start = self.OPENING[slot % len(self.OPENING)]
        return self._cycle[(self._start + turn) % len(self._cycle)]
