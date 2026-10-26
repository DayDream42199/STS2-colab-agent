from ._scripted import ScriptedEnemy, attack
from ...Effects.StatusEffects.territorial import Territorial


class Byrdonis(ScriptedEnemy):
    """Act 1 elite (ByrdonisElite). Swoop 17, then Peck 3 x 3, and again. It
    is Territorial: a Strength more at the end of every enemy turn."""

    NAME = "Byrdonis"
    CATEGORY = "elite"
    HP_RANGE = (81, 84)
    SWOOP = 17
    PECK = 3
    PECK_HITS = 3
    TERRITORIAL = 1

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._swoop = attack("Swoop", self.SWOOP)
        self._peck = attack("Peck", self.PECK, hits=self.PECK_HITS)

    def on_combat_start(self, context):
        return [Territorial(source=self, target=self, amount=self.TERRITORIAL)]

    def pick_move(self, turn):
        return self._swoop if turn % 2 == 0 else self._peck
