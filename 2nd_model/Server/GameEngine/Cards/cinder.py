from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_exhaust import InstantExhaust


class Cinder(Card):
    DAMAGE = 18

    def __init__(self):
        super().__init__(
            card_id = "cinder",
            name = "Cinder",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.COMMON,
            cost = 2,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        # Picked here rather than in the resolver, so the card owns the choice.
        hand = list(context.source.hand)
        picked = [context.rng.choice(hand)] if hand else []
        return [
            InstantDamage(
                source=context.source, target=context.target, amount=self.DAMAGE),
            InstantExhaust(
                source=context.source, target=context.source, card_ids=picked),
        ]
