from ._card import Card
from ..Effects.StatusEffects.free_attack import FreeAttack
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class Unrelenting(Card):
    DAMAGE = 14

    def __init__(self):
        super().__init__(
            card_id = "unrelenting",
            name = "Unrelenting",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 2,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        # A status the players can see, not a hidden counter: the game's
        # FreeAttackPower. Combat spends it on the next Attack played.
        return [
            InstantDamage(source=context.source, target=context.target, amount=self.DAMAGE),
            FreeAttack(source=context.source, target=context.source, amount=1),
        ]
