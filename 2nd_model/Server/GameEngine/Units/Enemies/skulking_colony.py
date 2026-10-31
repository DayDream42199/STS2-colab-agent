from ._scripted import ScriptedEnemy, attack
from ...Effects.StatusEffects.hardened_shell import HardenedShell
from ...Effects.StatusEffects.strength import Strength


class SkulkingColony(ScriptedEnemy):
    """Underdocks elite (SkulkingColonyElite). Hardened Shell 20: it loses at
    most 20 HP a turn (scaled with its HP in co-op). Zoom 14, Zoom 14, Inertia
    9 and +2 Strength, Piercing Stabs 7 x 2, round and round."""

    NAME = "Skulking Colony"
    CATEGORY = "elite"
    DEFAULT_MAX_HP = 75
    DEFAULT_HP_VARIANCE = 0
    HARDENED_SHELL = 20
    ZOOM = 14
    INERTIA = 9
    INERTIA_STRENGTH = 2
    PIERCING_STABS = 7
    PIERCING_STABS_HITS = 2

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        zoom = attack("Zoom", self.ZOOM)
        self._cycle = (zoom, attack("Zoom", self.ZOOM),
                       attack("Inertia", self.INERTIA, gain=(Strength, self.INERTIA_STRENGTH)),
                       attack("Piercing Stabs", self.PIERCING_STABS, hits=self.PIERCING_STABS_HITS))

    def on_combat_start(self, context):
        # The game scales Hardened Shell as it scales HP; the HP carries it.
        return [HardenedShell(source=self, target=self,
                              amount=round(self.HARDENED_SHELL * self.max_hp / self.DEFAULT_MAX_HP))]

    def pick_move(self, turn):
        return self._cycle[turn % len(self._cycle)]
