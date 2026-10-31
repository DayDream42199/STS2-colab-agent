from ._scripted import ScriptedEnemy, Move, attack, players, hand_out
from ...Effects.StatusEffects.weak import Weak


class HauntedShip(ScriptedEnemy):
    """Haunt once - 3 Weak and 5 Dazed into every discard pile - then Swipe
    13 and Stomp 4 x 3 in turn."""

    NAME = "Haunted Ship"
    DEFAULT_MAX_HP = 63
    DEFAULT_HP_VARIANCE = 0
    HAUNT_WEAK = 3
    HAUNT_DAZED = 5
    SWIPE = 13
    STOMP = 4
    STOMP_HITS = 3

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        dazed = hand_out("dazed", self.HAUNT_DAZED)
        self._haunt = Move("Haunt", Move.DEBUFF, lambda enemy, context: [
            Weak(source=enemy, target=p, amount=self.HAUNT_WEAK) for p in players(context)]
            + dazed(enemy, context))
        self._swipe = attack("Swipe", self.SWIPE)
        self._stomp = attack("Stomp", self.STOMP, hits=self.STOMP_HITS)

    def pick_move(self, turn):
        if turn == 0:
            return self._haunt
        return self._swipe if turn % 2 == 1 else self._stomp
