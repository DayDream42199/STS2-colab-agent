from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.StatusEffects.return_to_hand import ReturnToHand


class Bolas(Card):
    DAMAGE = 3

    def __init__(self):
        super().__init__(
            card_id = "bolas",
            name = "Bolas",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        # ReturnToHand holds this exact copy and claims it on the way out, so
        # it never reaches the discard pile.
        return [
            InstantDamage(
                source=context.source, target=context.target,
                amount=self.DAMAGE),
            ReturnToHand(
                source=context.source, target=context.source,
                card_ref=self.ref),
        ]
