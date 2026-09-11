"""Mad Science: one event card, eight printings.

The event decides which you get, so each is its own card id with its own
effects. They share the name so the card list counts them as one, and carry
VARIANT for anything that wants to tell them apart. TOKEN class: an event hands
them out, so "a random card" must never turn one up.
"""
from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_block import InstantBlock
from ..Effects.InstantEffects.instant_draw import InstantDraw
from ..Effects.InstantEffects.instant_energy import InstantEnergy
from ..Effects.InstantEffects.instant_add_card import InstantAddCard
from ..Effects.StatusEffects.weak import Weak
from ..Effects.StatusEffects.vulnerable import Vulnerable
from ..Effects.StatusEffects.strength import Strength
from ..Effects.StatusEffects.dexterity import Dexterity
from ..Effects.StatusEffects.choking import Choking
from ..Effects.StatusEffects.curious import Curious


class MadScience(Card):
    VARIANT = ""
    TYPE = CardType.SKILL
    TARGET = TargetType.SELF

    def __init__(self):
        super().__init__(
            card_id = "mad_science_" + self.VARIANT.lower(),
            name = "Mad Science",
            card_type = self.TYPE,
            card_class = CardClass.TOKEN,
            rarity = CardRarity.RARE,
            cost = 1,
            target_type = self.TARGET
        )


class MadScienceSapping(MadScience):
    VARIANT = "Sapping"
    TYPE = CardType.ATTACK
    TARGET = TargetType.ENEMY
    DAMAGE = 12
    WEAK = 2
    VULNERABLE = 2

    def get_effects(self, context):
        me, them = context.source, context.target
        return [
            InstantDamage(source=me, target=them, amount=self.DAMAGE),
            Weak(source=me, target=them, amount=self.WEAK),
            Vulnerable(source=me, target=them, amount=self.VULNERABLE),
        ]


class MadScienceViolence(MadScience):
    VARIANT = "Violence"
    TYPE = CardType.ATTACK
    TARGET = TargetType.ENEMY
    DAMAGE = 12
    HITS = 3

    def get_effects(self, context):
        return [
            InstantDamage(source=context.source, target=context.target,
                          amount=self.DAMAGE)
            for _ in range(self.HITS)
        ]


class MadScienceChoking(MadScience):
    VARIANT = "Choking"
    TYPE = CardType.ATTACK
    TARGET = TargetType.ENEMY
    DAMAGE = 12
    PER_CARD = 6

    def get_effects(self, context):
        me, them = context.source, context.target
        return [
            InstantDamage(source=me, target=them, amount=self.DAMAGE),
            Choking(source=me, target=me, amount=self.PER_CARD, victim=them),
        ]


class MadScienceEnergized(MadScience):
    VARIANT = "Energized"
    BLOCK = 8
    ENERGY = 2

    def get_effects(self, context):
        me = context.source
        return [
            InstantBlock(source=me, target=me, amount=self.BLOCK),
            InstantEnergy(source=me, target=me, amount=self.ENERGY),
        ]


class MadScienceWisdom(MadScience):
    VARIANT = "Wisdom"
    BLOCK = 8
    CARDS = 3

    def get_effects(self, context):
        me = context.source
        return [
            InstantBlock(source=me, target=me, amount=self.BLOCK),
            InstantDraw(source=me, target=me, amount=self.CARDS, rng=context.rng),
        ]


class MadScienceChaos(MadScience):
    VARIANT = "Chaos"
    BLOCK = 8

    def get_effects(self, context):
        from ..Registry.card_registry import generatable_card_ids

        me = context.source
        effects = [InstantBlock(source=me, target=me, amount=self.BLOCK)]
        pool = generatable_card_ids(card_class=CardClass.IRONCLAD)
        if pool:
            picked = context.rng.choice(pool)
            me.free_this_turn.append(picked)
            effects.append(InstantAddCard(
                source=me, target=me, card_id=picked, pile=InstantAddCard.HAND))
        return effects


class MadScienceExpertise(MadScience):
    VARIANT = "Expertise"
    STRENGTH = 2
    DEXTERITY = 2

    def get_effects(self, context):
        me = context.source
        return [
            Strength(source=me, target=me, amount=self.STRENGTH),
            Dexterity(source=me, target=me, amount=self.DEXTERITY),
        ]


class MadScienceCurious(MadScience):
    VARIANT = "Curious"
    TYPE = CardType.POWER
    DISCOUNT = 1

    def get_effects(self, context):
        me = context.source
        return [Curious(source=me, target=me, amount=self.DISCOUNT)]


VARIANTS = (
    MadScienceSapping, MadScienceViolence, MadScienceChoking,
    MadScienceEnergized, MadScienceWisdom, MadScienceChaos,
    MadScienceExpertise, MadScienceCurious,
)
