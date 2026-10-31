from ._scripted import ScriptedEnemy, Move, attack, debuff
from ...Effects.StatusEffects.shriek import Shriek
from ...Effects.StatusEffects.stun import Stun
from ...Effects.StatusEffects.vigor import Vigor
from ...Effects.StatusEffects.vulnerable import Vulnerable


class TerrorEel(ScriptedEnemy):
    """Underdocks elite (TerrorEelElite). Crash 16, then Thrash 3 x 3 and 6
    Vigor (its next attack +6), and again. Shriek 70: once it is down to 70
    HP it is stunned for a turn, then Terror - 99 Vulnerable on every player
    - then back to Crash. In co-op Shriek scales with its HP."""

    NAME = "Terror Eel"
    CATEGORY = "elite"
    DEFAULT_MAX_HP = 140
    DEFAULT_HP_VARIANCE = 0
    SHRIEK = 70
    CRASH = 16
    THRASH = 3
    THRASH_HITS = 3
    THRASH_VIGOR = 6
    TERROR_VULNERABLE = 99

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._crash = attack("Crash", self.CRASH)
        self._thrash = attack("Thrash", self.THRASH, hits=self.THRASH_HITS, gain=(Vigor, self.THRASH_VIGOR))
        self._terror = debuff("Terror", Vulnerable, self.TERROR_VULNERABLE)
        self._next = None

    def on_combat_start(self, context):
        # The game scales Shriek as it scales HP; the HP carries that factor.
        return [Shriek(source=self, target=self,
                       amount=round(self.SHRIEK * self.max_hp / self.DEFAULT_MAX_HP))]

    def shriek_broken(self):
        """Down to Shriek: stunned a turn, then Terror, then Crash."""
        self.apply_status(Stun(source=self, target=self, amount=1))
        self.move = self._terror
        self._next = self._crash

    def pick_move(self, turn):
        if self._next is not None:
            move, self._next = self._next, None
            return move
        if turn == 0 or self.history[-1] is not self._crash:
            return self._crash
        return self._thrash
