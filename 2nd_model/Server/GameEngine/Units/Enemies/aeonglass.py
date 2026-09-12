from ._scripted import ScriptedEnemy, Move
from ...Cards._card_ref import CardRef
from ...Effects.InstantEffects.instant_damage import InstantDamage
from ...Effects.InstantEffects.instant_block import InstantBlock
from ...Effects.InstantEffects.instant_add_card import InstantAddCard
from ...Effects.StatusEffects.strength import Strength


class Aeonglass(ScriptedEnemy):
    """Glory boss. A three-move cycle that gets worse each time round.

    Increasing Intensity hands one player a Wither that deals 3 + X at the end
    of any turn it is held, and gives Aeonglass 2 + X Strength, where X is how
    many times it has intensified: Wither, Wither+1, Wither+2...
    """

    CATEGORY = "boss"
    DEFAULT_MAX_HP = 512
    DEFAULT_HP_VARIANCE = 0

    EBB = 22
    EBB_BLOCK = 33
    LASER = 11
    LASER_HITS = 2
    INTENSITY_STRENGTH = 2

    def _ebb(self, context):
        effects = []
        if context.target is not None:
            effects.append(InstantDamage(
                source=self, target=context.target, amount=self.EBB))
        effects.append(InstantBlock(source=self, target=self, amount=self.EBB_BLOCK))
        return effects

    def _lasers(self, context):
        if context.target is None:
            return []
        return [InstantDamage(source=self, target=context.target, amount=self.LASER)
                for _ in range(self.LASER_HITS)]

    def _intensity(self, context):
        # Counted when the move resolves, not when it is announced: a stunned
        # turn must not advance it. get_effects runs once per enemy turn.
        x = self.intensity_uses
        self.intensity_uses += 1
        effects = [Strength(source=self, target=self,
                            amount=self.INTENSITY_STRENGTH + x)]
        if context.target is not None:
            effects.insert(0, InstantAddCard(
                source=self, target=context.target,
                card_id=CardRef("wither", bonus_damage=x),
                pile=InstantAddCard.DISCARD))
        return effects

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self.intensity_uses = 0
        ebb = Move("Ebb", Move.ATTACK, lambda e, c: e._ebb(c), damage=self.EBB)
        lasers = Move("Eye Lasers", Move.ATTACK, lambda e, c: e._lasers(c),
                      damage=self.LASER, hits=self.LASER_HITS)
        intensity = Move("Increasing Intensity", Move.DEBUFF,
                         lambda e, c: e._intensity(c), targeted=True)
        self._cycle = (ebb, lasers, intensity)

    def pick_move(self, turn):
        return self._cycle[turn % len(self._cycle)]
