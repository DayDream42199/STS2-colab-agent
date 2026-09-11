from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class Midnight(Card):
    DAMAGE = 60

    def __init__(self):
        super().__init__(
            card_id = "midnight",
            name = "Midnight",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 12,
            target_type = TargetType.ENEMY
        )

    def dynamic_cost(self, context):
        # "by ANYONE", so this reads the combat-wide tally rather than the
        # owner's own turn counters.
        return self.cost - context.counters.get("cards_exhausted", 0)

    def get_effects(self, context):
        return [InstantDamage(
            source=context.source, target=context.target, amount=self.DAMAGE)]
