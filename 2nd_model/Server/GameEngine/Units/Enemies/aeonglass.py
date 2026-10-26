from ._scripted import ScriptedEnemy, Move, players
from ...Cards._card_ref import CardRef
from ...Effects.InstantEffects.instant_damage import InstantDamage
from ...Effects.InstantEffects.instant_block import InstantBlock
from ...Effects.InstantEffects.instant_add_card import InstantAddCard
from ...Effects.InstantEffects.instant_boost_card import InstantBoostCard
from ...Effects.StatusEffects.strength import Strength
from ...Effects.StatusEffects.artifact import Artifact, artifact_for
from ...Effects.StatusEffects.withering_presence import WitheringPresence


class Aeonglass(ScriptedEnemy):
    """Glory boss, as the game's code has it. Ebb, Eye Lasers, Increasing
    Intensity, round and round, and it gets worse every time round.

    Increasing Intensity first upgrades every Wither already in play (each
    upgrade is +3 damage: Wither deals 3, Wither+1 6, Wither+2 9), then hands
    every player a Wither at the new level, then gains 3 Strength - 4 the
    next time, 5 the time after. On arrival it puts Withering Presence on
    every player (a Wither in hand every 6 cards they play) and takes 3
    Artifact, one more per extra player.
    """

    CATEGORY = "boss"
    DEFAULT_MAX_HP = 512
    DEFAULT_HP_VARIANCE = 0

    EBB = 26
    EBB_BLOCK = 33
    LASER = 11
    LASER_HITS = 2
    INTENSITY_STRENGTH = 3
    ARTIFACT = 3
    WITHER_STEP = 3              # damage per Wither upgrade

    def on_combat_start(self, context):
        effects = [WitheringPresence(source=self, target=p) for p in players(context)]
        effects.append(Artifact(source=self, target=self,
                                amount=artifact_for(len(context.all_allies), self.ARTIFACT)))
        return effects

    def _ebb(self, context):
        effects = [InstantDamage(source=self, target=p, amount=self.EBB)
                   for p in players(context)]
        effects.append(InstantBlock(source=self, target=self, amount=self.EBB_BLOCK))
        return effects

    def _lasers(self, context):
        return [InstantDamage(source=self, target=p, amount=self.LASER)
                for _ in range(self.LASER_HITS) for p in players(context)]

    def _intensity(self, context):
        # Counted when the move resolves, not when it is announced: a stunned
        # turn must not advance it. get_effects runs once per enemy turn.
        existing = [ref for p in context.all_allies
                    for pile in (p.hand, p.draw_pile, p.discard_pile, p.exhaust_pile)
                    for ref in pile if ref == "wither"]
        self.wither_upgrades += 1
        strength = self.INTENSITY_STRENGTH + self.additional_strength
        self.additional_strength += 1
        effects = []
        if existing:
            effects.append(InstantBoostCard(source=self, target=self, card_refs=existing,
                                            amount=self.WITHER_STEP))
        effects.extend(
            InstantAddCard(source=self, target=p, pile=InstantAddCard.DISCARD,
                           card_id=CardRef("wither",
                                           bonus_damage=self.WITHER_STEP * self.wither_upgrades))
            for p in players(context))
        effects.append(Strength(source=self, target=self, amount=strength))
        return effects

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        # How many times Intensity has upgraded the Withers, and the Strength
        # it adds on top of its 3 - both climb by one each time.
        self.wither_upgrades = 0
        self.additional_strength = 0
        ebb = Move("Ebb", Move.ATTACK, lambda e, c: e._ebb(c), damage=self.EBB,
                   block=self.EBB_BLOCK)
        lasers = Move("Eye Lasers", Move.ATTACK, lambda e, c: e._lasers(c),
                      damage=self.LASER, hits=self.LASER_HITS)
        intensity = Move("Increasing Intensity", Move.DEBUFF,
                         lambda e, c: e._intensity(c))
        self._cycle = (ebb, lasers, intensity)

    def pick_move(self, turn):
        return self._cycle[turn % len(self._cycle)]
