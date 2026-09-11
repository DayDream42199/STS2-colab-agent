from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_hp_loss import InstantHpLoss
from ..Effects.InstantEffects.instant_exhaust import InstantExhaust
from ..Effects.StatusEffects.strength import Strength


class Brand(Card):
    STRENGTH = 1

    def __init__(self):
        super().__init__(
            card_id = "brand",
            name = "Brand",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 0,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        # Picked here rather than in the resolver, so the card owns the choice.
        hand = list(context.source.hand)
        picked = [context.rng.choice(hand)] if hand else []
        return [
            InstantHpLoss(source=context.source, target=context.source, amount=1),
            InstantExhaust(
                source=context.source, target=context.source, card_ids=picked),
            Strength(
                source=context.source, target=context.source, amount=self.STRENGTH),
        ]
