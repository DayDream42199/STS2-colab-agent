from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock
from ..Effects.InstantEffects.instant_exhaust import InstantExhaust


class TrueGrit(Card):
    BLOCK = 7

    def __init__(self):
        super().__init__(
            card_id = "true_grit",
            name = "True Grit",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.COMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        ally = context.source
        effects = [InstantBlock(source=ally, target=ally, amount=self.BLOCK)]
        if not ally.hand:
            return effects
        if not self.upgraded:
            # The base printing says "at random", and means it.
            effects.append(InstantExhaust(
                source=ally, target=ally, card_ids=[context.rngs.card_selection.choice(ally.hand)]))
            return effects
        context.ask(ally, "Exhaust a card", lambda: list(ally.hand),
                    lambda chosen: [InstantExhaust(source=ally, target=ally, card_ids=[chosen])])
        return effects
