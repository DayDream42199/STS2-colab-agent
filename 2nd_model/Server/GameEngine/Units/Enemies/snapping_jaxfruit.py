from ._scripted import ScriptedEnemy, Move
from ...Effects.InstantEffects.instant_damage import InstantDamage
from ...Effects.StatusEffects.strength import Strength


class SnappingJaxfruit(ScriptedEnemy):
    """Act 1. One move, every turn: Energy Orb hits for 3, then the Jaxfruit
    gains 2 Strength - after the hit, so the orbs land for 3, 5, 7..."""

    NAME = "Snapping Jaxfruit"
    HP_RANGE = (31, 33)

    ORB = 3
    STRENGTH = 2

    def _energy_orb(self, context):
        effects = []
        if context.target is not None:
            effects.append(InstantDamage(source=self, target=context.target, amount=self.ORB))
        effects.append(Strength(source=self, target=self, amount=self.STRENGTH))
        return effects

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._orb = Move("Energy Orb", Move.ATTACK, lambda e, c: e._energy_orb(c),
                         damage=self.ORB)

    def pick_move(self, turn):
        return self._orb
