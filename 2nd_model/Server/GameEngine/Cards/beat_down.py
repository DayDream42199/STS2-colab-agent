from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_play_card import InstantPlayCard


class BeatDown(Card):
    COUNT = 3

    def __init__(self):
        super().__init__(
            card_id = "beat_down",
            name = "Beat Down",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.UNCOMMON,
            cost = 3,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        # Imported here, not at module level: the registry imports
        # this card, so importing it back at import time would deadlock.
        from ..Registry.card_registry import create_card

        attacks = [c for c in context.source.discard_pile
                   if create_card(c).card_type is CardType.ATTACK]
        if not attacks:
            return []
        picked = (attacks if len(attacks) <= self.COUNT
                  else context.rng.sample(attacks, self.COUNT))
        return [
            InstantPlayCard(source=context.source, target=context.source,
                            card_id=card_id,
                            from_pile=InstantPlayCard.DISCARD)
            for card_id in picked
        ]
