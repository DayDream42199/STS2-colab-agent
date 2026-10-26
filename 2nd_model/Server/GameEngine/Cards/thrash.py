from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_exhaust import InstantExhaust
from ..Effects.InstantEffects.instant_boost_card import InstantBoostCard


class Thrash(Card):
    DAMAGE = 4
    HITS = 2

    def __init__(self):
        super().__init__(
            card_id = "thrash",
            name = "Thrash",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        from ..Registry.card_registry import create_card
        ally = context.source
        # Hit first, at what this copy has grown to so far.
        effects = [
            InstantDamage(source=ally, target=context.target,
                          amount=self.DAMAGE + self.bonus_damage)
            for _ in range(self.HITS)
        ]
        attacks = [ref for ref in ally.hand
                   if create_card(ref).card_type is CardType.ATTACK]
        if not attacks:
            return effects
        # Then eat a random Attack and keep its damage on this copy for the
        # rest of the combat, as the game does - the NEXT Thrash hits harder,
        # not this one. The eaten card's damage counts your Strength and
        # Weak, with no target to count Vulnerable against.
        from ..Resolution.resolver import Resolver
        chosen = context.rngs.card_selection.choice(attacks)
        eaten = create_card(chosen)
        gain = Resolver.damage_amount(ally, None, eaten.DAMAGE + eaten.bonus_damage)
        effects.append(InstantExhaust(source=ally, target=ally, card_ids=[chosen]))
        effects.append(InstantBoostCard(source=ally, target=ally,
                                        card_refs=[self.ref], amount=gain))
        return effects
