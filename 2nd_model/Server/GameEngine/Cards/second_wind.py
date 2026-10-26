from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_block import InstantBlock
from ..Effects.InstantEffects.instant_exhaust import InstantExhaust


class SecondWind(Card):
    BLOCK_PER_CARD = 5

    def __init__(self):
        super().__init__(
            card_id = "second_wind",
            name = "Second Wind",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    @staticmethod
    def _doomed(ally):
        """Every non-Attack in hand. This card is not among them: it has left
        the hand when it plays, and Combat.hand_blocks lifts it out the same
        way while its Block is shown."""
        from ..Registry.card_registry import create_card
        return [c for c in ally.hand if create_card(c).card_type is not CardType.ATTACK]

    def base_block(self, ally):
        return self.BLOCK_PER_CARD * len(self._doomed(ally))

    def block_gains(self, ally):
        # One gain per card, so Dexterity and Frail apply to each.
        return [(self.BLOCK_PER_CARD, True)] * len(self._doomed(ally))

    def get_effects(self, context):
        # Attacks stay; everything else burns - each exhausted, then its
        # Block gained, one card at a time, as the game's SecondWind does.
        effects = []
        for card_id in self._doomed(context.source):
            effects.append(InstantExhaust(
                source=context.source, target=context.source, card_ids=[card_id]))
            effects.append(InstantBlock(
                source=context.source, target=context.source, amount=self.BLOCK_PER_CARD))
        return effects
