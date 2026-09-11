from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_ref import replay_of
from ..Effects.InstantEffects.instant_grant_replay import InstantGrantReplay


class HiddenGem(Card):
    REPLAY = 2

    def __init__(self):
        super().__init__(
            card_id = "hidden_gem",
            name = "Hidden Gem",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        ally = context.source
        # Only a card that has none: Replay does not stack up on one copy.
        candidates = [ref for ref in ally.draw_pile if replay_of(ref) == 0]
        if not candidates:
            return []
        return [InstantGrantReplay(
            source=ally, target=ally,
            card_refs=[context.rng.choice(candidates)], amount=self.REPLAY)]
