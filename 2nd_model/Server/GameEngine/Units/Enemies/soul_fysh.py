from ._scripted import ScriptedEnemy, Move, attack, buff, hand_out, players
from ...Effects.InstantEffects.instant_add_card import InstantAddCard
from ...Effects.StatusEffects.intangible import Intangible
from ...Effects.StatusEffects.vulnerable import Vulnerable


class SoulFysh(ScriptedEnemy):
    """Underdocks boss (SoulFyshBoss). Beckon - a Beckon shuffled into each
    player's draw pile and one into the discard - then De-Gas 16, Gaze 7 and
    a Beckon into the discard, Fade (2 Intangible: the players' next turn
    deals it 1 a hit), Scream 13 and 3 Vulnerable, and round again. A Beckon
    held at the end of a turn costs 6 HP; it can be played for 1."""

    NAME = "Soul Fysh"
    CATEGORY = "boss"
    DEFAULT_MAX_HP = 211
    DEFAULT_HP_VARIANCE = 0
    DE_GAS = 16
    GAZE = 7
    SCREAM = 13
    SCREAM_VULNERABLE = 3
    FADE_INTANGIBLE = 2

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        gaze = attack("Gaze", self.GAZE)
        self._cycle = (
            Move("Beckon", Move.DEBUFF, self._beckon_effects),
            attack("De-Gas", self.DE_GAS),
            Move("Gaze", Move.ATTACK, lambda enemy, context:
                 gaze.effects(enemy, context) + hand_out("beckon")(enemy, context),
                 damage=self.GAZE),
            buff("Fade", Intangible, self.FADE_INTANGIBLE),
            attack("Scream", self.SCREAM, inflict=(Vulnerable, self.SCREAM_VULNERABLE)),
        )

    @staticmethod
    def _beckon_effects(enemy, context):
        out = []
        for p in players(context):
            # At a random depth, by the Shuffle stream (CardPilePosition.Random).
            out.append(InstantAddCard(source=enemy, target=p, card_id="beckon",
                                      pile=InstantAddCard.DRAW, rng=context.rngs.shuffle))
            out.append(InstantAddCard(source=enemy, target=p, card_id="beckon",
                                      pile=InstantAddCard.DISCARD))
        return out

    def pick_move(self, turn):
        return self._cycle[turn % len(self._cycle)]
