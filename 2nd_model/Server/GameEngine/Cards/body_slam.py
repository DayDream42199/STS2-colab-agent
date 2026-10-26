from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage

class BodySlam(Card):
    def __init__(self):
        super().__init__(
            card_id = "body_slam",
            name = "Body Slam",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def base_damage(self, ally):
        # Damage is read off live state at play time, not fixed on the card.
        return ally.block

    def get_effects(self, context):
        return [InstantDamage(
            source=context.source,
            target=context.target,
            amount=self.base_damage(context.source),
        )]
