from ._scripted import ScriptedEnemy, attack, debuff
from ...Effects.StatusEffects.shrink import Shrink


class ShrinkerBeetle(ScriptedEnemy):
    """Act 1. Opens by Shrinking every player - their Attacks deal 30% less
    for as long as the Beetle lives (the game applies -1, which never wears
    off) - then alternates Chomp (7) and Stomp (13)."""

    NAME = "Shrinker Beetle"
    HP_RANGE = (38, 40)

    SHRINK = -1                  # permanent: see Shrink
    CHOMP = 7
    STOMP = 13

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._opener = debuff("Shrinker", Shrink, self.SHRINK)
        self._cycle = (attack("Chomp", self.CHOMP), attack("Stomp", self.STOMP))

    def pick_move(self, turn):
        if turn == 0:
            return self._opener
        return self._cycle[(turn - 1) % len(self._cycle)]
