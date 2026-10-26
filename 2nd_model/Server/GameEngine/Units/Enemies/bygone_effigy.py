from ._scripted import ScriptedEnemy, Move, attack, buff
from ...Effects.StatusEffects.slow import Slow
from ...Effects.StatusEffects.strength import Strength


class BygoneEffigy(ScriptedEnemy):
    """Act 1 elite (BygoneEffigyElite). Asleep the first turn, wakes with 10
    Strength, then Slashes 13 every turn after. It is Slow: every card played
    in a turn makes attacks on it 10% stronger that turn."""

    NAME = "Bygone Effigy"
    CATEGORY = "elite"
    DEFAULT_MAX_HP = 127
    DEFAULT_HP_VARIANCE = 0
    WAKE_STRENGTH = 10
    SLASHES = 13

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._sleep = Move("Sleep", Move.SLEEP, lambda enemy, context: [])
        self._wake = buff("Wake", Strength, self.WAKE_STRENGTH)
        self._slashes = attack("Slashes", self.SLASHES)

    def on_combat_start(self, context):
        return [Slow(source=self, target=self)]

    def pick_move(self, turn):
        if turn == 0:
            return self._sleep
        if turn == 1:
            return self._wake
        return self._slashes
