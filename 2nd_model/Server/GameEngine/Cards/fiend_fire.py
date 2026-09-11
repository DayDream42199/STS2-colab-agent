from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_exhaust import InstantExhaust


class FiendFire(Card):
    DAMAGE_PER_CARD = 7

    def __init__(self):
        super().__init__(
            card_id = "fiend_fire",
            name = "Fiend Fire",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 2,
            target_type = TargetType.ENEMY,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        # This card is already out of hand by the time effects resolve, so it
        # never burns itself.
        doomed = list(context.source.hand)
        effects = [InstantExhaust(
            source=context.source, target=context.source, card_ids=doomed)]
        effects.extend(
            InstantDamage(source=context.source, target=context.target,
                          amount=self.DAMAGE_PER_CARD)
            for _ in range(len(doomed))
        )
        return effects
