from ._scripted import ScriptedEnemy, Move, attack
from ...Effects.InstantEffects.instant_summon import InstantSummon
from ...Effects.StatusEffects.strength import Strength
from ...Effects.StatusEffects.surprise import Surprise
from ...Effects.StatusEffects.weak import Weak


class GremlinMerc(ScriptedEnemy):
    """Underdocks (GremlinMercNormal). Gimme 7 x 2, Double Smash 6 x 2 and 2
    Weak, Hehe 8 and +2 Strength, round and round. Surprise: when it dies a
    Sneaky Gremlin and a Fat Gremlin jump in, and the fight goes on. The game
    also has it steal gold, which this engine does not keep."""

    NAME = "Gremlin Merc"
    HP_RANGE = (47, 49)
    GIMME = 7
    GIMME_HITS = 2
    DOUBLE_SMASH = 6
    DOUBLE_SMASH_HITS = 2
    DOUBLE_SMASH_WEAK = 2
    HEHE = 8
    HEHE_STRENGTH = 2

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._cycle = (attack("Gimme", self.GIMME, hits=self.GIMME_HITS),
                       attack("Double Smash", self.DOUBLE_SMASH, hits=self.DOUBLE_SMASH_HITS,
                              inflict=(Weak, self.DOUBLE_SMASH_WEAK)),
                       attack("Hehe", self.HEHE, gain=(Strength, self.HEHE_STRENGTH)))

    def on_combat_start(self, context):
        return [Surprise(source=self, target=self)]

    def pick_move(self, turn):
        return self._cycle[turn % len(self._cycle)]

    def on_death(self, context):
        return [InstantSummon(source=self, type_ids=[SneakyGremlin.type_id(), FatGremlin.type_id()])]


class _Spawned(ScriptedEnemy):
    """A gremlin the Merc's Surprise brings in: its first turn it only gets
    its bearings (the game's SPAWNED_MOVE, shown as a stun)."""

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._spawned = Move("Spawned", "stun", lambda enemy, context: [])


class SneakyGremlin(_Spawned):
    """Spawned, then Tackle 9 every turn."""

    NAME = "Sneaky Gremlin"
    HP_RANGE = (10, 14)
    TACKLE = 9

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._tackle = attack("Tackle", self.TACKLE)

    def pick_move(self, turn):
        return self._spawned if turn == 0 else self._tackle


class FatGremlin(_Spawned):
    """Spawned, then it flees: gone from the fight, not killed."""

    NAME = "Fat Gremlin"
    HP_RANGE = (13, 17)

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._flee = Move("Flee", "escape", lambda enemy, context: enemy.escape() or [])

    def pick_move(self, turn):
        return self._spawned if turn == 0 else self._flee
