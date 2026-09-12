from ._scripted import ScriptedEnemy, Move, attack, hand_out
from ...Effects.StatusEffects.strength import Strength


class Wriggler(ScriptedEnemy):
    """Act 1. Wriggle hands one player an Infection and takes 2 Strength for
    itself; Nasty Bite follows, and so on. Phrog Parasite spawns four of these
    at once, which is when the Strength starts to matter."""

    HP_RANGE = (17, 21)

    NASTY_BITE = 6
    STRENGTH = 2

    def _wriggle(self, context):
        effects = hand_out("infection")(self, context)
        effects.append(Strength(source=self, target=self, amount=self.STRENGTH))
        return effects

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        wriggle = Move("Wriggle", Move.DEBUFF, lambda e, c: e._wriggle(c), targeted=True)
        self._cycle = (wriggle, attack("Nasty Bite", self.NASTY_BITE))

    def pick_move(self, turn):
        return self._cycle[turn % len(self._cycle)]
