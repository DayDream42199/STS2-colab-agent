from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_ref import replay_of
from ..Effects.InstantEffects.instant_grant_replay import InstantGrantReplay


class HiddenGem(Card):
    GENERATED_IN_COMBAT = False     # never made at random (CanBeGeneratedInCombat)
    REPLAY = 2

    def __init__(self):
        super().__init__(
            card_id = "hidden_gem",
            name = "Hidden Gem",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.RARE,
            cost = 1,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        ally = context.source
        # Imported here, not at module level: card_registry imports this
        # module, so a top-level import would be circular.
        from ..Registry.card_registry import create_card

        # Only a card that has none: Replay does not stack up on one copy.
        # And one that can be played and is not a Curse; an Attack, Skill or
        # Power over a Status whenever there is one (the game's Hidden Gem).
        candidates = [ref for ref in ally.draw_pile
                      if replay_of(ref) == 0 and create_card(ref).properties.playable
                      and create_card(ref).card_type is not CardType.CURSE]
        preferred = [ref for ref in candidates
                     if create_card(ref).card_type is not CardType.STATUS]
        candidates = preferred or candidates
        if not candidates:
            return []
        return [InstantGrantReplay(
            source=ally, target=ally,
            card_refs=[context.rngs.card_selection.choice(candidates)], amount=self.REPLAY)]
