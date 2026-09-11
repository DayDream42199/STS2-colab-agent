from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.StatusEffects.weak import Weak
from ..Effects.StatusEffects.vulnerable import Vulnerable


class Shockwave(Card):
    AMOUNT = 3

    def __init__(self):
        super().__init__(
            card_id = "shockwave",
            name = "Shockwave",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 2,
            target_type = TargetType.ALL_ENEMIES,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        effects = []
        for enemy in context.all_enemies:
            if not enemy.is_alive():
                continue
            effects.append(Weak(
                source=context.source, target=enemy, amount=self.AMOUNT))
            effects.append(Vulnerable(
                source=context.source, target=enemy, amount=self.AMOUNT))
        return effects
