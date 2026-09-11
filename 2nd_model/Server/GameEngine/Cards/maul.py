from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_boost_card import InstantBoostCard


class Maul(Card):
    DAMAGE = 5
    HITS = 2
    BONUS = 2

    def __init__(self):
        super().__init__(
            card_id = "maul",
            name = "Maul",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.ANCIENT,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        ally = context.source
        damage = self.DAMAGE + self.bonus_damage
        effects = [
            InstantDamage(source=ally, target=context.target, amount=damage)
            for _ in range(self.HITS)
        ]
        # Every Maul, not just this one, and the exhaust pile counts too: a
        # Maul that comes back later arrives already carrying the growth.
        copies = [ref
                  for pile in (ally.hand, ally.draw_pile, ally.discard_pile,
                               ally.exhaust_pile)
                  for ref in pile if ref == self.card_id]
        copies.append(self.ref)   # this one is in flight, in no pile
        effects.append(InstantBoostCard(
            source=ally, target=ally, card_refs=copies, amount=self.BONUS))
        return effects
