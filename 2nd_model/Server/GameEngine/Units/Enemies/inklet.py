from ._scripted import ScriptedEnemy, Branch, attack
from ...Effects.StatusEffects.slippery import Slippery, slippery_for


class Inklet(ScriptedEnemy):
    """Act 1 (Overgrowth), three at a time (InkletsNormal). Arrives Slippery:
    the first hit that gets through takes 1 HP (one per player in co-op).
    Jab 3, then at random Piercing Gaze 10 or Whirlwind 2 x 3, then Jab again,
    and so on. The middle one of three opens with Whirlwind."""

    NAME = "Inklet"
    HP_RANGE = (11, 17)
    JAB = 3
    WHIRLWIND = 2
    WHIRLWIND_HITS = 3
    PIERCING_GAZE = 10
    SLIPPERY = 1

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._jab = attack("Jab", self.JAB)
        self._whirlwind = attack("Whirlwind", self.WHIRLWIND, hits=self.WHIRLWIND_HITS)
        self._gaze = attack("Piercing Gaze", self.PIERCING_GAZE)
        # The game's "RAND" state; neither can follow itself, but a Jab always
        # comes between, so it is an even pick.
        self._after_jab = (Branch(self._gaze, Branch.NO_REPEAT),
                           Branch(self._whirlwind, Branch.NO_REPEAT))

    def on_combat_start(self, context):
        return [Slippery(source=self, target=self,
                         amount=slippery_for(len(context.all_allies), self.SLIPPERY))]

    def pick_move(self, turn):
        if turn == 0:
            # InkletsNormal marks the second of its three as MiddleInklet.
            return self._whirlwind if self.same_kind_index(self.context) == 1 else self._jab
        if self.history[-1] is self._jab:
            return self.choose(self._after_jab)
        return self._jab
