from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_draw import InstantDraw
from ..Effects.StatusEffects.no_more_draw import NoMoreDraw


class BattleTrance(Card):
    CARDS = 3

    def __init__(self):
        super().__init__(
            card_id = "battle_trance",
            name = "Battle Trance",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 0,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        # Draw first, then the lockout, or the card cancels its own draw.
        return [
            InstantDraw(source=context.source, target=context.source,
                        amount=self.CARDS, rng=context.rng),
            NoMoreDraw(source=context.source, target=context.source, amount=1),
        ]
