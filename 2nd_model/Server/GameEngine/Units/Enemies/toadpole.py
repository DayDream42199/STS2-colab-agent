from ._scripted import ScriptedEnemy, Move, attack, buff
from ...Effects.StatusEffects.caltrops import Caltrops


class Toadpole(ScriptedEnemy):
    """Underdocks, two of them (ToadpolesWeak). Spiken (+2 Thorns), Spike Spit
    3 x 3 - shedding those 2 Thorns first - and Whirl 7, round and round. The
    front one opens with Spiken, the back one with Whirl. Thorns is the game's
    ThornsPower, our Caltrops: attacked, it deals that much back."""

    NAME = "Toadpole"
    HP_RANGE = (21, 25)
    SPIKEN = 2
    SPIKE_SPIT = 3
    SPIKE_SPIT_HITS = 3
    WHIRL = 7

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        spit = attack("Spike Spit", self.SPIKE_SPIT, hits=self.SPIKE_SPIT_HITS)
        self._spiken = buff("Spiken", Caltrops, self.SPIKEN)
        self._spike_spit = Move("Spike Spit", Move.ATTACK, lambda enemy, context: [
            Caltrops(source=enemy, target=enemy, amount=-self.SPIKEN)] + spit.effects(enemy, context),
            damage=self.SPIKE_SPIT, hits=self.SPIKE_SPIT_HITS)
        self._whirl = attack("Whirl", self.WHIRL)
        self._cycle = (self._whirl, self._spiken, self._spike_spit)
        self._start = 0

    def pick_move(self, turn):
        if turn == 0:
            # ToadpolesWeak makes the first of the two IsFront.
            self._start = 1 if self.same_kind_index(self.context) == 0 else 0
        return self._cycle[(self._start + turn) % len(self._cycle)]
