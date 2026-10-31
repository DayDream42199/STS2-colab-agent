from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_damage import InstantDamage


class GangUp(Card):
    MULTIPLAYER_ONLY = True         # a co-op card: not made at random solo
    DAMAGE = 5
    PER_ALLY = 5

    def __init__(self):
        super().__init__(
            card_id = "gang_up",
            name = "Gang Up",
            card_type = CardType.ATTACK,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.ENEMY
        )

    def get_effects(self, context):
        # Per hit another player landed on it this turn, as the game counts
        # (DamageReceivedEntry, powered attacks): a Twin Strike is two.
        attackers = context.target.turn_counters.get("attacked_by", ())
        others = sum(1 for a in attackers if a is not context.source)
        return [InstantDamage(
            source=context.source,
            target=context.target,
            amount=self.DAMAGE + others * self.PER_ALLY,
        )]
