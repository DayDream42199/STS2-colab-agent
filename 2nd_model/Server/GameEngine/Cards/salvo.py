from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class Salvo(Card):
    DAMAGE = 12

    def __init__(self):
        super().__init__(
            card_id = "salvo",
            name = "Salvo",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        context.source.retain_hand = True
        return [InstantDamage(
            source=context.source, target=context.target, amount=self.DAMAGE)]
