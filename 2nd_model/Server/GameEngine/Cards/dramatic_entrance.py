from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_damage import InstantDamage


class DramaticEntrance(Card):
    DAMAGE = 11

    def __init__(self):
        super().__init__(
            card_id = "dramatic_entrance",
            name = "Dramatic Entrance",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.ALL_ENEMIES,
            properties = CardProperties(exhaust=True, innate=True)
        )

    def get_effects(self, context):
        return [
            InstantDamage(
                source=context.source, target=enemy, amount=self.DAMAGE)
            for enemy in context.all_enemies
            if enemy.is_alive()
        ]
