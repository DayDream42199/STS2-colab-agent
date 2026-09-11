from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.StatusEffects.vulnerable import Vulnerable


class MoltenFist(Card):
    DAMAGE = 10

    def __init__(self):
        super().__init__(
            card_id = "molten_fist",
            name = "Molten Fist",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.ENEMY,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        effects = [InstantDamage(
            source=context.source, target=context.target, amount=self.DAMAGE)]
        # Doubling means applying again however much is already there.
        vulnerable = context.target.get_status("vulnerable")
        if vulnerable and vulnerable.amount > 0:
            effects.append(Vulnerable(
                source=context.source, target=context.target,
                amount=vulnerable.amount))
        return effects
