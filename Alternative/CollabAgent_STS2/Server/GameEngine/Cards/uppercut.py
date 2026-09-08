from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.StatusEffects.weak import Weak
from ..Effects.StatusEffects.vulnerable import Vulnerable

class Uppercut(Card):
    DAMAGE = 13
    WEAK = 1
    VULNERABLE = 1

    def __init__(self):
        super().__init__(
            card_id = "uppercut",
            name = "Uppercut",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 2,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        return [
            InstantDamage(
                source=context.source, target=context.target, amount=self.DAMAGE),
            Weak(source=context.source, target=context.target, amount=self.WEAK),
            Vulnerable(
                source=context.source, target=context.target, amount=self.VULNERABLE),
        ]
