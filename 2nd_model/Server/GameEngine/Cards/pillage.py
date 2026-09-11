from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_draw_until import InstantDrawUntil


class Pillage(Card):
    DAMAGE = 6

    def __init__(self):
        super().__init__(
            card_id = "pillage",
            name = "Pillage",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        return [
            InstantDamage(
                source=context.source, target=context.target, amount=self.DAMAGE),
            InstantDrawUntil(
                source=context.source, target=context.source,
                while_type=CardType.ATTACK, rng=context.rng),
        ]
