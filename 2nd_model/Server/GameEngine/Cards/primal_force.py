from ._card import Card
from ._card_enums import CardType, CardClass, CardRarity, TargetType
from ..Effects.InstantEffects.instant_move_card import InstantMoveCard
from ..Effects.InstantEffects.instant_add_card import InstantAddCard


class PrimalForce(Card):
    def __init__(self):
        super().__init__(
            card_id = "primal_force",
            name = "Primal Force",
            card_type = CardType.SKILL,
            card_class = CardClass.IRONCLAD,
            rarity = CardRarity.RARE,
            cost = 0,
            target_type = TargetType.SELF
        )

    def get_effects(self, context):
        # Imported here rather than at module level: the registry imports this
        # card, so importing it back at import time would deadlock.
        from ..Registry.card_registry import create_card

        attacks = [card_id for card_id in context.source.hand
                   if create_card(card_id).card_type is CardType.ATTACK]
        if not attacks:
            return []
        return [
            # GONE, not EXHAUST: a transform replaces the cards rather than
            # exhausting them, so "whenever you exhaust" powers stay quiet.
            InstantMoveCard(
                source=context.source, target=context.source, card_ids=attacks,
                from_pile=InstantMoveCard.HAND, to_pile=InstantMoveCard.GONE),
            InstantAddCard(
                source=context.source, target=context.source,
                card_id="giant_rock", pile=InstantAddCard.HAND,
                amount=len(attacks)),
        ]
