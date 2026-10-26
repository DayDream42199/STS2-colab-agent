"""Act 1 raiders. They turn up in mixed groups; each is a two-beat pattern."""
from ._scripted import ScriptedEnemy, attack, buff, debuff, guard
from ...Effects.StatusEffects.strength import Strength
from ...Effects.StatusEffects.frail import Frail


class AssassinRaider(ScriptedEnemy):
    """Killshot, 10, every turn. 18-23 HP - kill it first."""

    NAME = "Assassin Raider"
    HP_RANGE = (18, 23)

    KILLSHOT = 10

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._killshot = attack("Killshot", self.KILLSHOT)

    def pick_move(self, turn):
        return self._killshot


class AxeRaider(ScriptedEnemy):
    """Swing (5, and 5 Block), Swing again, then Big Swing (12)."""

    NAME = "Axe Raider"
    HP_RANGE = (20, 22)

    SWING = 5
    SWING_BLOCK = 5
    BIG_SWING = 12

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        swing = attack("Swing", self.SWING, block=self.SWING_BLOCK)
        self._cycle = (swing, swing, attack("Big Swing", self.BIG_SWING))

    def pick_move(self, turn):
        return self._cycle[turn % len(self._cycle)]


class BruteRaider(ScriptedEnemy):
    """Beat (7), Roar (+3 Strength), alternating."""

    NAME = "Brute Raider"
    HP_RANGE = (30, 33)

    BEAT = 7
    ROAR = 3

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._cycle = (attack("Beat", self.BEAT), buff("Roar", Strength, self.ROAR))

    def pick_move(self, turn):
        return self._cycle[turn % len(self._cycle)]


class TrackerRaider(ScriptedEnemy):
    """Track (2 Frail on every player) once, then Unleash the Hounds (1 x 8)
    every turn after. Eight small bites: every point of Strength counts eight
    times, and Block soaks them one at a time."""

    NAME = "Tracker Raider"
    HP_RANGE = (21, 25)

    FRAIL = 2
    HOUND = 1
    HOUNDS = 8

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._track = debuff("Track", Frail, self.FRAIL)
        self._hounds = attack("Unleash the Hounds", self.HOUND, hits=self.HOUNDS)

    def pick_move(self, turn):
        return self._track if turn == 0 else self._hounds


class CrossbowRaider(ScriptedEnemy):
    """Reload (3 Block), Fire! (14), alternating. The Block is gone by the
    time it fires - an enemy's Block clears at the start of its own turn."""

    NAME = "Crossbow Raider"
    HP_RANGE = (18, 21)

    RELOAD_BLOCK = 3
    FIRE = 14

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._cycle = (guard("Reload", self.RELOAD_BLOCK), attack("Fire!", self.FIRE))

    def pick_move(self, turn):
        return self._cycle[turn % len(self._cycle)]
