from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class Spite(Card):
    DAMAGE = 5
    HITS_IF_HURT = 2

    def __init__(self):
        super().__init__(
            card_id = "spite",
            name = "Spite",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        hits = self.HITS_IF_HURT if context.source.turn_count("hp_lost") else 1
        return [
            InstantDamage(
                source=context.source, target=context.target, amount=self.DAMAGE)
            for _ in range(hits)
        ]
