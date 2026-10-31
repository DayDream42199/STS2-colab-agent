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
            rarity = CardRarity.RARE,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def base_damage(self, ally):
        # Cards played before this one, by the whole team (the game's
        # CardPlaysFinished): the count goes up after it resolves.
        return ally.combat_count("team_cards_played")

    def get_effects(self, context):
        return [InstantDamage(
            source=context.source,
            target=context.target,
            amount=self.base_damage(context.source),
        )]
