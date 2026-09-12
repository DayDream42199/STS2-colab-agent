from ._scripted import ScriptedEnemy, attack
from ...Effects.StatusEffects.tangled import Tangled


class VineShambler(ScriptedEnemy):
    """Act 1. A three-beat cycle from turn 1: Swipe (6 x 2), Grasping Vines
    (8, and Tangled - Attacks cost 1 more), Chomp (16).

    The reference applies 1 Tangled where its own note quotes the wiki as
    "for 2 turns"; the reference's number is used here (`TANGLED`)."""

    NAME = "Vine Shambler"
    DEFAULT_MAX_HP = 61
    DEFAULT_HP_VARIANCE = 0

    SWIPE = 6
    SWIPE_HITS = 2
    VINES = 8
    TANGLED = 1
    CHOMP = 16

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._cycle = (attack("Swipe", self.SWIPE, hits=self.SWIPE_HITS),
                       attack("Grasping Vines", self.VINES, inflict=(Tangled, self.TANGLED)),
                       attack("Chomp", self.CHOMP))

    def pick_move(self, turn):
        return self._cycle[turn % len(self._cycle)]
