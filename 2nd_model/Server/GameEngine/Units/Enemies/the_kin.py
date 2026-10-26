from ._scripted import ScriptedEnemy, attack, buff
from ...Effects.StatusEffects.frail import Frail
from ...Effects.StatusEffects.minion import Minion
from ...Effects.StatusEffects.strength import Strength
from ...Effects.StatusEffects.weak import Weak


class KinPriest(ScriptedEnemy):
    """Act 1 boss (TheKinBoss), behind two Kin Followers. Orb of Frailty 8
    (+1 Frail), Orb of Weakness 8 (+1 Weak), Beam 3 x 3, Ritual +2 Strength,
    round and round. When it falls, its followers go with it."""

    NAME = "Kin Priest"
    CATEGORY = "boss"
    DEFAULT_MAX_HP = 190
    DEFAULT_HP_VARIANCE = 0
    ORB = 8
    BEAM = 3
    BEAM_HITS = 3
    RITUAL_STRENGTH = 2

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._cycle = (attack("Orb of Frailty", self.ORB, inflict=(Frail, 1)),
                       attack("Orb of Weakness", self.ORB, inflict=(Weak, 1)),
                       attack("Beam", self.BEAM, hits=self.BEAM_HITS),
                       buff("Ritual", Strength, self.RITUAL_STRENGTH))

    def pick_move(self, turn):
        return self._cycle[turn % len(self._cycle)]


class KinFollower(ScriptedEnemy):
    """The Kin Priest's followers, two of them; Minions, so they leave when
    the Priest dies. Quick Slash 5, Boomerang 2 x 2, Power Dance +2 Strength,
    round and round - the first of the two opens with the Dance."""

    NAME = "Kin Follower"
    HP_RANGE = (58, 59)
    QUICK_SLASH = 5
    BOOMERANG = 2
    BOOMERANG_HITS = 2
    DANCE_STRENGTH = 2

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._cycle = (attack("Quick Slash", self.QUICK_SLASH),
                       attack("Boomerang", self.BOOMERANG, hits=self.BOOMERANG_HITS),
                       buff("Power Dance", Strength, self.DANCE_STRENGTH))
        self._start = 0

    def on_combat_start(self, context):
        return [Minion(source=self, target=self)]

    def pick_move(self, turn):
        if turn == 0:
            # TheKinBoss sets StartsWithDance on the one in the first slot.
            self._start = 2 if self.same_kind_index(self.context) == 0 else 0
        return self._cycle[(self._start + turn) % len(self._cycle)]
