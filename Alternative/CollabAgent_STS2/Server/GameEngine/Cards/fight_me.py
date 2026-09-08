from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.StatusEffects.strength import Strength

class FightMe(Card):
    DAMAGE = 5
    HITS = 2
    STRENGTH = 3
    ENEMY_STRENGTH = 1

    def __init__(self):
        super().__init__(
            card_id = "fight_me",
            name = "Fight Me!",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        effects = [
            InstantDamage(
                source=context.source, target=context.target, amount=self.DAMAGE)
            for _ in range(self.HITS)
        ]
        # Both sides get Strength: it is a taunt, not a pure buff.
        effects.append(Strength(
            source=context.source, target=context.source, amount=self.STRENGTH))
        effects.append(Strength(
            source=context.source, target=context.target, amount=self.ENEMY_STRENGTH))
        return effects
