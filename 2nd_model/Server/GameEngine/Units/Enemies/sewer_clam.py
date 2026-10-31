from ._scripted import ScriptedEnemy, attack, buff
from ...Effects.InstantEffects.instant_block import InstantBlock
from ...Effects.StatusEffects.plating import Plating, plating_for
from ...Effects.StatusEffects.strength import Strength


class SewerClam(ScriptedEnemy):
    """Arrives with 8 Plating, and behind that much Block. Jet 10, then
    Pressurize (+4 Strength), and again."""

    NAME = "Sewer Clam"
    DEFAULT_MAX_HP = 56
    DEFAULT_HP_VARIANCE = 0
    PLATING = 8
    JET = 10
    PRESSURIZE_STRENGTH = 4

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._jet = attack("Jet", self.JET)
        self._pressurize = buff("Pressurize", Strength, self.PRESSURIZE_STRENGTH)

    def on_combat_start(self, context):
        plating = plating_for(len(context.all_allies), self.PLATING)
        return [Plating(source=self, target=self, amount=plating),
                InstantBlock(source=self, target=self, amount=plating, powered=False, card=False)]

    def pick_move(self, turn):
        return self._jet if turn % 2 == 0 else self._pressurize
