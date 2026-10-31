from ._scripted import ScriptedEnemy, Move, attack
from ...Effects.InstantEffects.instant_block import InstantBlock
from ...Effects.StatusEffects.strength import Strength


class Seapunk(ScriptedEnemy):
    """Sea Kick 11, Spinning Kick 2 x 4, Bubble Burp (7 Block, +1 Strength),
    round and round."""

    NAME = "Seapunk"
    HP_RANGE = (44, 46)
    SEA_KICK = 11
    SPINNING_KICK = 2
    SPINNING_KICK_HITS = 4
    BUBBLE_BLOCK = 7
    BUBBLE_STRENGTH = 1

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._cycle = (
            attack("Sea Kick", self.SEA_KICK),
            attack("Spinning Kick", self.SPINNING_KICK, hits=self.SPINNING_KICK_HITS),
            Move("Bubble Burp", Move.BUFF, lambda enemy, context: [
                InstantBlock(source=enemy, target=enemy, amount=self.BUBBLE_BLOCK),
                Strength(source=enemy, target=enemy, amount=self.BUBBLE_STRENGTH)],
                block=self.BUBBLE_BLOCK))

    def pick_move(self, turn):
        return self._cycle[turn % len(self._cycle)]
