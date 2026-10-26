from ._scripted import ScriptedEnemy, Move, attack, hand_out
from ..Enemies.wriggler import Wriggler
from ...Effects.InstantEffects.instant_summon import InstantSummon
from ...Effects.StatusEffects.infested import Infested


class PhrogParasite(ScriptedEnemy):
    """Act 1 elite (PhrogParasiteElite). Infect - 3 Infection into every
    player's discard pile - then Lash 4 x 4, and again. It is Infested: when
    it dies four Wrigglers burst out, stunned for their first turn, and the
    fight goes on until they are dead too."""

    NAME = "Phrog Parasite"
    CATEGORY = "elite"
    HP_RANGE = (61, 64)
    INFECTION = 3
    LASH = 4
    LASH_HITS = 4
    WRIGGLERS = 4

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._infect = Move("Infect", Move.DEBUFF, hand_out("infection", self.INFECTION))
        self._lash = attack("Lash", self.LASH, hits=self.LASH_HITS)

    def on_combat_start(self, context):
        return [Infested(source=self, target=self, amount=self.WRIGGLERS)]

    def pick_move(self, turn):
        return self._infect if turn % 2 == 0 else self._lash

    def on_death(self, context):
        # Four, whatever Infested shows (InfestedPower always makes four).
        # Not Minions: they are enemies in their own right.
        return [InstantSummon(source=self, type_ids=[Wriggler.type_id()] * self.WRIGGLERS,
                              stunned=True)]
