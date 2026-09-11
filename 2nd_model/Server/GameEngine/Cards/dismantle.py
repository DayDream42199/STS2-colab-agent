from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class Dismantle(Card):
    DAMAGE = 8

    def __init__(self):
        super().__init__(
            card_id = "dismantle",
            name = "Dismantle",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        hits = 2 if context.target.get_status("vulnerable") else 1
        return [
            InstantDamage(
                source=context.source, target=context.target, amount=self.DAMAGE)
            for _ in range(hits)
        ]
