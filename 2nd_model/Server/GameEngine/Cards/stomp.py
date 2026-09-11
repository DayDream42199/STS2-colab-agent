from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class Stomp(Card):
    DAMAGE = 12

    def __init__(self):
        super().__init__(
            card_id = "stomp",
            name = "Stomp",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 3,
            target_type = TargetType.ALL_ENEMIES
        )

    def dynamic_cost(self, context):
        # attacks_played is tallied by Combat on every CARD_PLAYED, and
        # turn_counters are wiped at the start of each turn.
        return self.cost - context.source.turn_count("attacks_played")

    def get_effects(self, context):
        return [
            InstantDamage(
                source=context.source, target=enemy, amount=self.DAMAGE)
            for enemy in context.all_enemies
            if enemy.is_alive()
        ]
