from ._scripted import ScriptedEnemy, Move, attack, hand_out
from ...Effects.StatusEffects.strength import Strength


class Wriggler(ScriptedEnemy):
    """Act 1. Wriggle (an Infection to every player, +2 Strength) and Nasty
    Bite (6), alternating. Which comes first depends on the slot, as in the
    game: the 1st and 3rd Wriggler of a group bite first, the 2nd and 4th
    wriggle first. Phrog Parasite's four arrive stunned."""

    HP_RANGE = (17, 21)

    NASTY_BITE = 6
    STRENGTH = 2

    def _wriggle(self, context):
        effects = hand_out("infection")(self, context)
        effects.append(Strength(source=self, target=self, amount=self.STRENGTH))
        return effects

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._bite = attack("Nasty Bite", self.NASTY_BITE)
        self._wriggle_move = Move("Wriggle", Move.DEBUFF, lambda e, c: e._wriggle(c))

    def pick_move(self, turn):
        if not self.history:
            first_bites = self.same_kind_index(self.context) % 2 == 0
            return self._bite if first_bites else self._wriggle_move
        return self._wriggle_move if self.history[-1] is self._bite else self._bite
