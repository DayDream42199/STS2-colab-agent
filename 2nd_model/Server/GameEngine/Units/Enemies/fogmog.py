from ._scripted import ScriptedEnemy, Move, Branch, attack, hand_out
from ...Effects.InstantEffects.instant_summon import InstantSummon
from ...Effects.StatusEffects.illusion import Illusion
from ...Effects.StatusEffects.strength import Strength


class Fogmog(ScriptedEnemy):
    """Act 1 (Overgrowth), alone (FogmogNormal). Opens with Illusion, calling
    in an Eye With Teeth; then Swipe 8 (+1 Strength); then at random Headbutt
    14 (60%) or a second Swipe that Headbutt always follows; then Swipe again.
    Killing Fogmog takes the Eye with it."""

    NAME = "Fogmog"
    DEFAULT_MAX_HP = 74
    DEFAULT_HP_VARIANCE = 0
    SWIPE = 8
    SWIPE_STRENGTH = 1
    HEADBUTT = 14

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._illusion = Move("Illusion", Move.SUMMON, lambda enemy, context: [
            # The Eye's Illusion makes it a Minion, so it leaves with Fogmog.
            InstantSummon(source=enemy, type_ids=[EyeWithTeeth.type_id()], minion=True)])
        self._swipe = attack("Swipe", self.SWIPE, gain=(Strength, self.SWIPE_STRENGTH))
        # A move of its own in the game (SWIPE_RANDOM_MOVE), so it does not
        # count as a repeat of the Swipe before it.
        self._swipe_again = attack("Swipe", self.SWIPE, gain=(Strength, self.SWIPE_STRENGTH))
        self._headbutt = attack("Headbutt", self.HEADBUTT)
        self._branches = (Branch(self._swipe_again, Branch.NO_REPEAT, weight=0.4),
                          Branch(self._headbutt, Branch.NO_REPEAT, weight=0.6))

    def pick_move(self, turn):
        if turn == 0:
            return self._illusion
        last = self.history[-1]
        if last is self._swipe:
            return self.choose(self._branches)
        if last is self._swipe_again:
            return self._headbutt
        return self._swipe              # after Illusion, and after either Headbutt


class EyeWithTeeth(ScriptedEnemy):
    """Fogmog's Illusion. 6 HP; Distract puts 3 Dazed in every player's
    discard pile, every turn. Killed, it is back at full HP for the next turn
    - unless Fogmog is dead too."""

    NAME = "Eye With Teeth"
    DEFAULT_MAX_HP = 6
    DEFAULT_HP_VARIANCE = 0
    DAZED = 3

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._distract = Move("Distract", Move.DEBUFF, hand_out("dazed", self.DAZED))

    def on_combat_start(self, context):
        return [Illusion(source=self, target=self)]

    def pick_move(self, turn):
        return self._distract
