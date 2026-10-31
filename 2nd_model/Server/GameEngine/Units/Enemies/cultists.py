from ._scripted import ScriptedEnemy, attack, buff
from ...Effects.StatusEffects.ritual import Ritual


class _Cultist(ScriptedEnemy):
    """Incantation - Ritual: Strength at the end of every enemy turn from the
    next on - then Dark Strike every turn."""

    RITUAL = 0
    DARK_STRIKE = 0

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._incantation = buff("Incantation", Ritual, self.RITUAL)
        self._dark_strike = attack("Dark Strike", self.DARK_STRIKE)

    def pick_move(self, turn):
        return self._incantation if turn == 0 else self._dark_strike


class CalcifiedCultist(_Cultist):
    """Ritual 2, Dark Strike 9."""

    NAME = "Calcified Cultist"
    HP_RANGE = (38, 41)
    RITUAL = 2
    DARK_STRIKE = 9


class DampCultist(_Cultist):
    """Ritual 5, Dark Strike 1."""

    NAME = "Damp Cultist"
    HP_RANGE = (51, 53)
    RITUAL = 5
    DARK_STRIKE = 1
