from ._scripted import ScriptedEnemy, Move, attack, players
from ...Effects.InstantEffects.instant_damage import InstantDamage
from ...Effects.InstantEffects.instant_hp_loss import InstantHpLoss
from ...Effects.InstantEffects.instant_summon import InstantSummon
from ...Effects.StatusEffects.smoggy import Smoggy


class LivingFog(ScriptedEnemy):
    """Underdocks (LivingFogNormal). Advanced Gas 8 and Smoggy on every
    player - one Skill a turn from then on - then Bloat and Super Gas Blast
    in turn: Bloat sets down a Gas Bomb and hits for 5, Super Gas Blast hits
    for 8. The bombs are its Minions and go when it does."""

    NAME = "Living Fog"
    DEFAULT_MAX_HP = 80
    DEFAULT_HP_VARIANCE = 0
    ADVANCED_GAS = 8
    BLOAT = 5
    SUPER_GAS_BLAST = 8
    # The encounter's bomb slots: no bomb is set down while all five are taken.
    BOMB_SLOTS = 5

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._advanced_gas = attack("Advanced Gas", self.ADVANCED_GAS, inflict=(Smoggy, 1))
        self._bloat = Move("Bloat", Move.ATTACK, self._bloat_effects, damage=self.BLOAT)
        self._super_gas_blast = attack("Super Gas Blast", self.SUPER_GAS_BLAST)

    def _bloat_effects(self, enemy, context):
        # The bomb first, then the hit, as the game's BloatMove.
        out = []
        bombs = [e for e in context.all_enemies if isinstance(e, GasBomb) and e.is_alive()]
        if len(bombs) < self.BOMB_SLOTS:
            out.append(InstantSummon(source=enemy, type_ids=[GasBomb.type_id()], minion=True))
        out.extend(InstantDamage(source=enemy, target=p, amount=self.BLOAT) for p in players(context))
        return out

    def pick_move(self, turn):
        if turn == 0:
            return self._advanced_gas
        return self._bloat if turn % 2 == 1 else self._super_gas_blast


class GasBomb(ScriptedEnemy):
    """Living Fog's bomb, a Minion. Its one move is Explode: 8 to every
    player, and it is gone."""

    NAME = "Gas Bomb"
    DEFAULT_MAX_HP = 7
    DEFAULT_HP_VARIANCE = 0
    EXPLODE = 8

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._explode = Move("Explode", Move.ATTACK, self._explode_effects, damage=self.EXPLODE)

    def _explode_effects(self, enemy, context):
        out = [InstantDamage(source=enemy, target=p, amount=self.EXPLODE) for p in players(context)]
        # Then it kills itself (CreatureCmd.Kill): every HP it has, whatever
        # it has been hit for since.
        out.append(InstantHpLoss(source=enemy, target=enemy, amount=enemy.max_hp))
        return out

    def pick_move(self, turn):
        return self._explode
