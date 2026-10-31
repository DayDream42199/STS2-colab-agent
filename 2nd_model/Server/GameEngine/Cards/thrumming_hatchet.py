from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.StatusEffects.return_to_hand import ReturnToHand


class ThrummingHatchet(Card):
    DAMAGE = 11

    def __init__(self):
        super().__init__(
            card_id = "thrumming_hatchet",
            name = "Thrumming Hatchet",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        # It goes to the discard pile as usual; ReturnToHand holds this exact
        # copy and brings it back next turn from wherever it is by then.
        return [
            InstantDamage(
                source=context.source, target=context.target,
                amount=self.DAMAGE),
            ReturnToHand(
                source=context.source, target=context.source,
                card_ref=self.ref),
        ]
