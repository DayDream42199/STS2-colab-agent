from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_hp_loss import InstantHpLoss
from ..Effects.InstantEffects.instant_exhaust import InstantExhaust
from ..Effects.StatusEffects.strength import Strength


class Brand(Card):
    HP_LOSS = 1
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
        ally = context.source
        strength = Strength(source=ally, target=ally, amount=self.STRENGTH)
        effects = [InstantHpLoss(source=ally, target=ally, amount=self.HP_LOSS)]
        if not ally.hand:
            return effects + [strength]

        # Lose HP, choose, exhaust, then the Strength - the game's order.
        def exhaust(chosen):
            return [InstantExhaust(source=ally, target=ally, card_ids=[chosen]), strength]

        context.ask(ally, "Exhaust a card", lambda: list(ally.hand), exhaust)
        return effects
