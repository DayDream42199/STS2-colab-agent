from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_boost_card import InstantBoostCard


class Rampage(Card):
    DAMAGE = 10
    INCREASE = 5

    def __init__(self):
        super().__init__(
            card_id = "rampage",
            name = "Rampage",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        # The growth is on this copy alone: a second Rampage in the deck still
        # opens at 10 however often this one has been played.
        return [
            InstantDamage(
                source=context.source, target=context.target,
                amount=self.DAMAGE + self.bonus_damage),
            InstantBoostCard(
                source=context.source, target=context.source,
                card_refs=[self.ref], amount=self.INCREASE),
        ]
