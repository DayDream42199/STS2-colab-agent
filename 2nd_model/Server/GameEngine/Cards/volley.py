from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class Volley(Card):
    DAMAGE = 10

    def __init__(self):
        super().__init__(
            card_id = "volley",
            name = "Volley",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = Card.X_COST,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        # Re-rolled per hit, so the shots can land on different enemies.
        effects = []
        for _ in range(context.x_amount):
            living = [e for e in context.all_enemies if e.is_alive()]
            if not living:
                break
            effects.append(InstantDamage(
                source=context.source, target=context.rng.choice(living),
                amount=self.DAMAGE))
        return effects
