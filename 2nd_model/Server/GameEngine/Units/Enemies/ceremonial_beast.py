from ._scripted import ScriptedEnemy, Move, attack, debuff
from ...Effects.StatusEffects.plow import Plow
from ...Effects.StatusEffects.ringing import Ringing
from ...Effects.StatusEffects.strength import Strength
from ...Effects.StatusEffects.stun import Stun


class CeremonialBeast(ScriptedEnemy):
    """Act 1 boss (CeremonialBeastBoss), in two phases.

    First it Stamps - Plow 150 on itself - then Plows every turn: 18 and +2
    Strength. Once its HP is down to the Plow number the charge breaks: it
    loses all its Strength and is stunned for a turn. Then, round and round,
    Beast Cry (Ringing on every player: one card next turn), Stomp 15, Crush
    17 and +3 Strength. In co-op Plow scales with its HP, so the break comes
    at the same share of its health."""

    NAME = "Ceremonial Beast"
    CATEGORY = "boss"
    DEFAULT_MAX_HP = 252
    DEFAULT_HP_VARIANCE = 0
    PLOW = 150
    PLOW_DAMAGE = 18
    PLOW_STRENGTH = 2
    STOMP = 15
    CRUSH = 17
    CRUSH_STRENGTH = 3

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._stamp = Move("Stamp", Move.BUFF, lambda enemy, context: [
            Plow(source=enemy, target=enemy, amount=enemy._plow_amount())])
        self._plow = attack("Plow", self.PLOW_DAMAGE, gain=(Strength, self.PLOW_STRENGTH))
        self._second_phase = (debuff("Beast Cry", Ringing, 1),
                              attack("Stomp", self.STOMP),
                              attack("Crush", self.CRUSH, gain=(Strength, self.CRUSH_STRENGTH)))
        self.in_second_phase = False
        self._step = 0

    def _plow_amount(self):
        # The game scales Plow as it scales HP (players x the act's factor);
        # the HP already carries that factor, so Plow takes the same ratio.
        return round(self.PLOW * self.max_hp / self.DEFAULT_MAX_HP)

    def plow_broken(self):
        """Plow says the charge broke: stunned a turn, then Beast Cry - the
        move the game's stun hands back to."""
        self.in_second_phase = True
        self.apply_status(Stun(source=self, target=self, amount=1))
        self.move = self._second_phase[0]
        self._step = 1

    def pick_move(self, turn):
        if not self.in_second_phase:
            return self._stamp if turn == 0 else self._plow
        move = self._second_phase[self._step % len(self._second_phase)]
        self._step += 1
        return move
