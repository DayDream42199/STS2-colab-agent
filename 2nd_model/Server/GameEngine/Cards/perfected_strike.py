from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage

class PerfectedStrike(Card):
    DAMAGE = 6
    EXTRA_PER_STRIKE = 2

    def __init__(self):
        super().__init__(
            card_id = "perfected_strike",
            name = "Perfected Strike",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.COMMON,
            cost = 2,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        # Counts the whole deck, not just the hand. Card ids are snake_case,
        # so "strike" catches Strike, Twin Strike, Pommel Strike and the rest.
        strikes = sum(1 for card_id in context.source.deck if "strike" in card_id)
        return [InstantDamage(
            source=context.source,
            target=context.target,
            amount=self.DAMAGE + self.EXTRA_PER_STRIKE * strikes,
        )]
