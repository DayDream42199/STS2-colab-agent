from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class HandOfGreed(Card):
    DAMAGE = 20

    def __init__(self):
        super().__init__(
            card_id = "hand_of_greed",
            name = "Hand of Greed",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 2,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        # The gold clause has no map layer to pay out into, so only the
        # damage is modelled - as in the reference engine.
        return [InstantDamage(
            source=context.source, target=context.target, amount=self.DAMAGE)]
