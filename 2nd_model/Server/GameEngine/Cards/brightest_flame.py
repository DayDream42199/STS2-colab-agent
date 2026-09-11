from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_energy import InstantEnergy
from ..Effects.InstantEffects.instant_draw import InstantDraw
from ..Effects.InstantEffects.instant_max_hp_loss import InstantMaxHpLoss


class BrightestFlame(Card):
    ENERGY = 2
    CARDS = 2
    MAX_HP_LOSS = 1

    def __init__(self):
        super().__init__(
            card_id = "brightest_flame",
            name = "Brightest Flame",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.ANCIENT,
            cost = 0,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        return [
            InstantEnergy(
                source=context.source, target=context.source, amount=self.ENERGY),
            InstantDraw(source=context.source, target=context.source,
                        amount=self.CARDS, rng=context.rng),
            InstantMaxHpLoss(
                source=context.source, target=context.source, amount=self.MAX_HP_LOSS),
        ]
