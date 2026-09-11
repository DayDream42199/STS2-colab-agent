from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_add_card import InstantAddCard


class Calamity(StatusEffect):
    """Whenever you play an Attack, add a random Attack into your Hand."""

    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat

    def __init__(self, source, target, amount):
        super().__init__("calamity")
        self.source = source
        self.target = target
        self.amount = amount

    def on_event(self, event, context):
        # Imported here, not at module level: the registry imports the cards
        # that import this, so importing it back at import time would deadlock.
        from ...Registry.card_registry import generatable_card_ids
        from ...Cards._card_enums import CardClass, CardType

        if event is not GameEvent.CARD_PLAYED:
            return None
        if context.target is not context.source:
            return None
        card = context.payload.get("card")
        if card is None or card.card_type is not CardType.ATTACK:
            return None
        pool = generatable_card_ids(
            card_class=CardClass.IRONCLAD, card_type=CardType.ATTACK)
        if not pool:
            return None
        return [InstantAddCard(
            source=context.source, target=context.source,
            card_id=context.rng.choice(pool), pile=InstantAddCard.HAND)]
