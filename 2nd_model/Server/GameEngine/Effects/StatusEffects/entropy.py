from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_add_card import InstantAddCard
from ..InstantEffects.instant_move_card import InstantMoveCard


class Entropy(StatusEffect):
    """At the start of your turn, Transform 1 card in your Hand.

    Transform is GONE plus an add, so the old card is replaced rather than
    exhausted. What it turns into stays random - the card only lets you pick
    which one goes."""

    def on_owner_turn_end(self):
        pass

    def __init__(self, source, target, amount):
        super().__init__("entropy")
        self.source = source
        self.target = target
        self.amount = amount

    def on_event(self, event, context):
        from ...Registry.card_registry import generatable_card_ids
        from ...Cards._card_enums import CardClass

        if event is not GameEvent.TURN_START:
            return None
        if context.target is not context.source:
            return None
        ally = context.source
        pool = generatable_card_ids(card_class=CardClass.IRONCLAD)
        if not ally.hand or not pool:
            return None
        replacement = context.rng.choice(pool)

        def transform(chosen):
            return [
                InstantMoveCard(
                    source=ally, target=ally, card_ids=[chosen],
                    from_pile=InstantMoveCard.HAND,
                    to_pile=InstantMoveCard.GONE),
                InstantAddCard(
                    source=ally, target=ally, card_id=replacement,
                    pile=InstantAddCard.HAND),
            ]

        context.ask(ally, "Transform a card in your Hand",
                    lambda: list(ally.hand), transform)
        return None
