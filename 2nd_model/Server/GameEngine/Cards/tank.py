from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.StatusEffects.tank import Tank as TankStatus
from ..Effects.StatusEffects.protected import Protected


class Tank(Card):
    def __init__(self):
        super().__init__(
            card_id = "tank",
            name = "Tank",
            card_type = CardType.POWER,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        # We soak more; everyone else soaks less.
        effects = [TankStatus(
            source=context.source, target=context.source, amount=1)]
        for ally in context.all_allies:
            if ally is not context.source and ally.is_alive():
                effects.append(Protected(
                    source=context.source, target=ally, amount=1))
        return effects
