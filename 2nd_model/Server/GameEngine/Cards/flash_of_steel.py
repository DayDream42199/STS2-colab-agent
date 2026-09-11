from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_draw import InstantDraw


class FlashOfSteel(Card):
    DAMAGE = 5
    CARDS = 1

    def __init__(self):
        super().__init__(
            card_id = "flash_of_steel",
            name = "Flash of Steel",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        return [
            InstantDamage(source=context.source, target=context.target, amount=self.DAMAGE),
            InstantDraw(source=context.source, target=context.source,
                        amount=self.CARDS, rng=context.rng),
        ]
