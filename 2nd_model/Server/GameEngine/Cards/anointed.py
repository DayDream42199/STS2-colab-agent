from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ._card_properties import CardProperties
from ..Effects.InstantEffects.instant_move_card import InstantMoveCard


class Anointed(Card):
    def __init__(self):
        super().__init__(
            card_id = "anointed",
            name = "Anointed",
            card_type = CardType.SKILL,
            card_class = CardClass.COLORLESS,
            rarity = CardRarity.RARE,
            cost = 1,
            target_type = TargetType.SELF,
            properties = CardProperties(exhaust=True)
        )

    def get_effects(self, context):
        # Imported here, not at module level: card_registry imports this
        # module, so a top-level import would be circular.
        from ..Registry.card_registry import create_card
        # Random Rares from the pile, as many as the hand has room for; the
        # rest stay where they are (the game's TakeRandom(room), CombatCardSelection).
        ally = context.source
        rares = [c for c in ally.draw_pile
                 if create_card(c).rarity is CardRarity.RARE]
        room = max(0, ally.HAND_LIMIT - len(ally.hand))
        picked = context.rngs.card_selection.sample(rares, min(room, len(rares)))
        if not picked:
            return []
        return [InstantMoveCard(
            source=context.source, target=context.source, card_ids=picked,
            from_pile=InstantMoveCard.DRAW, to_pile=InstantMoveCard.HAND,
        )]
