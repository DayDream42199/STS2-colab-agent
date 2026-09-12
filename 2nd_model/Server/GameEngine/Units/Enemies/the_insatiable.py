from ._scripted import ScriptedEnemy, Move
from ...Effects.InstantEffects.instant_damage import InstantDamage
from ...Effects.InstantEffects.instant_add_card import InstantAddCard
from ...Effects.StatusEffects.sandpit import Sandpit
from ...Effects.StatusEffects.strength import Strength


class TheInsatiable(ScriptedEnemy):
    """Hive boss. Opens by liquifying the ground, then cycles through bites.

    Liquify gives every living player 4 Sandpit and six Frantic Escape: three
    at the BOTTOM of the draw pile and three in the discard, as the reference
    does - the escapes are not handed to you, you have to dig for them.
    """

    CATEGORY = "boss"
    DEFAULT_MAX_HP = 321
    DEFAULT_HP_VARIANCE = 0

    SANDPIT = 4
    ESCAPES_EACH = 3
    THRASH = 8
    THRASH_HITS = 2
    LUNGE = 28
    SALIVATE = 2

    def _liquify(self, context):
        effects = []
        for ally in context.all_allies:
            if not ally.is_alive():
                continue
            effects.append(Sandpit(source=self, target=ally, amount=self.SANDPIT))
            effects.append(InstantAddCard(
                source=self, target=ally, card_id="frantic_escape",
                pile=InstantAddCard.DRAW, amount=self.ESCAPES_EACH, bottom=True))
            effects.append(InstantAddCard(
                source=self, target=ally, card_id="frantic_escape",
                pile=InstantAddCard.DISCARD, amount=self.ESCAPES_EACH))
        return effects

    def _thrash(self, context):
        if context.target is None:
            return []
        return [InstantDamage(source=self, target=context.target, amount=self.THRASH)
                for _ in range(self.THRASH_HITS)]

    def _lunge(self, context):
        if context.target is None:
            return []
        return [InstantDamage(source=self, target=context.target, amount=self.LUNGE)]

    def _salivate(self, context):
        return [Strength(source=self, target=self, amount=self.SALIVATE)]

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        liquify = Move("Liquify Ground", Move.DEBUFF, lambda e, c: e._liquify(c))
        thrash = Move("Thrash", Move.ATTACK, lambda e, c: e._thrash(c),
                      damage=self.THRASH, hits=self.THRASH_HITS)
        lunge = Move("Lunging Bite", Move.ATTACK, lambda e, c: e._lunge(c),
                     damage=self.LUNGE)
        salivate = Move("Salivate", Move.BUFF, lambda e, c: e._salivate(c))
        self._opener = liquify
        self._cycle = (thrash, lunge, salivate, thrash)

    def pick_move(self, turn):
        if turn == 0:
            return self._opener
        return self._cycle[(turn - 1) % len(self._cycle)]
