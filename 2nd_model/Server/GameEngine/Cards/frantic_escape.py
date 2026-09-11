from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_raise_cost import InstantRaiseCost
from ..Effects.StatusEffects.sandpit import Sandpit


class FranticEscape(Card):
    """The Insatiable's status card: buy a turn, and pay more for the next one.

    Unlike the other status cards it is playable - playing it is the point."""

    TURNS = 1
    COST_RISE = 1

    def __init__(self):
        super().__init__(
            card_id = "frantic_escape",
            name = "Frantic Escape",
            card_type = CardType.STATUS,
            card_class = CardClass.STATUS,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        ally = context.source
        return [
            # Adds to the Sandpit already on you. Played with none - which
            # only a test can arrange, since the boss hands both out together -
            # it would start a one-turn countdown, exactly as in the reference.
            Sandpit(source=ally, target=ally, amount=self.TURNS),
            InstantRaiseCost(
                source=ally, target=ally, card_refs=[self.ref],
                amount=self.COST_RISE),
        ]
