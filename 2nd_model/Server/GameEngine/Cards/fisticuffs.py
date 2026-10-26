from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_block import InstantBlock


class Fisticuffs(Card):
    DAMAGE = 7

    def __init__(self):
        super().__init__(
            card_id = "fisticuffs",
            name = "Fisticuffs",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def base_block(self, ally):
        # The damage it deals, as far as it is known before a target is
        # chosen: after this player's Strength and Weak. The target's
        # Vulnerable can only add to it, once there is one.
        from ..Resolution.resolver import Resolver
        return Resolver.damage_amount(ally, None, self.base_damage(ally))

    def get_effects(self, context):
        return [InstantDamage(
            source=context.source, target=context.target, amount=self.DAMAGE)]

    def follow_up(self, result, context):
        # `total`, not `amount`: damage dealt counts what Block soaked up too.
        dealt = result.get("total", 0)
        if result["effect_id"] != "instant_damage" or dealt <= 0:
            return None
        return [InstantBlock(
            source=context.source, target=context.source, amount=dealt)]
