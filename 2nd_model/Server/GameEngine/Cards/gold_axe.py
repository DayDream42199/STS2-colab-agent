from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class GoldAxe(Card):
    def __init__(self):
        super().__init__(
            card_id = "gold_axe",
            name = "Gold Axe",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        return [InstantDamage(
            source=context.source,
            target=context.target,
            amount=context.source.combat_count("cards_played"),
        )]
