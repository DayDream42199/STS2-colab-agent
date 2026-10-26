from ._scripted import ScriptedEnemy, Move, attack, buff, hand_out
from ...Effects.StatusEffects.slippery import Slippery, slippery_for
from ...Effects.StatusEffects.strength import Strength


class Vantom(ScriptedEnemy):
    """Act 1 boss (VantomBoss). Arrives with 8 Slippery - the first eight
    hits that get through take 1 HP each (times the player count in co-op).
    Ink Blot 7, Inky Lance 6 x 2, Dismember 26 and 3 Wounds into every
    player's discard pile, Prepare +2 Strength, round and round."""

    NAME = "Vantom"
    CATEGORY = "boss"
    DEFAULT_MAX_HP = 173
    DEFAULT_HP_VARIANCE = 0
    SLIPPERY = 8
    INK_BLOT = 7
    INKY_LANCE = 6
    INKY_LANCE_HITS = 2
    DISMEMBER = 26
    WOUNDS = 3
    PREPARE_STRENGTH = 2

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        dismember = attack("Dismember", self.DISMEMBER)
        wounds = hand_out("wound", self.WOUNDS)
        self._cycle = (attack("Ink Blot", self.INK_BLOT),
                       attack("Inky Lance", self.INKY_LANCE, hits=self.INKY_LANCE_HITS),
                       Move("Dismember", Move.ATTACK,
                            lambda enemy, context: dismember.effects(enemy, context) + wounds(enemy, context),
                            damage=self.DISMEMBER),
                       buff("Prepare", Strength, self.PREPARE_STRENGTH))

    def on_combat_start(self, context):
        return [Slippery(source=self, target=self,
                         amount=slippery_for(len(context.all_allies), self.SLIPPERY))]

    def pick_move(self, turn):
        return self._cycle[turn % len(self._cycle)]
