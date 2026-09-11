from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_damage import InstantDamage
from ..Effects.StatusEffects.stun import Stun


class Whistle(Card):
    DAMAGE = 33
    TURNS = 1

    def __init__(self):
        super().__init__(
            card_id = "whistle",
            name = "Whistle",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.ANCIENT,
            cost = 2,
            target_type = TargetType.ENEMY,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        # Damage first: the resolver drops a status aimed at something already
        # dead, so a stun on a corpse costs nothing and reads correctly.
        return [
            InstantDamage(
                source=context.source, target=context.target, amount=self.DAMAGE),
            Stun(source=context.source, target=context.target, amount=self.TURNS),
        ]
