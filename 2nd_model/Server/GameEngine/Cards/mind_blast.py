from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_damage import InstantDamage


class MindBlast(Card):
    def __init__(self):
        super().__init__(
            card_id = "mind_blast",
            name = "Mind Blast",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ENEMY,
            properties = CardProperties(innate=True)
        )

    def base_damage(self, ally):
        return len(ally.draw_pile)

    def get_effects(self, context):
        return [InstantDamage(
            source=context.source,
            target=context.target,
            amount=self.base_damage(context.source),
        )]
