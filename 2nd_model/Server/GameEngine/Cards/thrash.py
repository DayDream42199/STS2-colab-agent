from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_exhaust import InstantExhaust


class Thrash(Card):
    DAMAGE = 4
    HITS = 2

    def __init__(self):
        super().__init__(
            card_id = "thrash",
            name = "Thrash",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        from ..Registry.card_registry import create_card

        ally = context.source
        attacks = [ref for ref in ally.hand
                   if create_card(ref).card_type is CardType.ATTACK]
        effects, bonus = [], 0
        if attacks:
            chosen = context.rng.choice(attacks)
            # The eaten card's own damage, so an upgraded one feeds more. A
            # card that works its damage out rather than printing it feeds 0.
            bonus = create_card(chosen).DAMAGE
            effects.append(InstantExhaust(
                source=ally, target=ally, card_ids=[chosen]))
        effects.extend(
            InstantDamage(source=ally, target=context.target,
                          amount=self.DAMAGE + bonus)
            for _ in range(self.HITS)
        )
        return effects
