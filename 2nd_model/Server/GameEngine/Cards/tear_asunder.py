from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class TearAsunder(Card):
    DAMAGE = 5

    def __init__(self):
        super().__init__(
            card_id = "tear_asunder",
            name = "Tear Asunder",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 2,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        # Times you lost HP, not how much: one extra hit per event.
        hits = 1 + context.source.combat_count("hp_lost_events")
        return [
            InstantDamage(
                source=context.source, target=context.target, amount=self.DAMAGE)
            for _ in range(hits)
        ]
