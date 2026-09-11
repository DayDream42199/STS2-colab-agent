from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.InstantEffects.instant_max_hp_gain import InstantMaxHpGain


class Feed(Card):
    DAMAGE = 10
    MAX_HP = 3

    def __init__(self):
        super().__init__(
            card_id = "feed",
            name = "Feed",
            card_type = CardType.ATTACK,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 1,
            target_type = TargetType.ENEMY,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        return [InstantDamage(
            source=context.source, target=context.target, amount=self.DAMAGE)]

    def follow_up(self, result, context):
        if result["effect_id"] != "instant_damage" or not result.get("killed"):
            return None
        return [InstantMaxHpGain(
            source=context.source, target=context.source, amount=self.MAX_HP)]
