from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_add_card import InstantAddCard
from ..InstantEffects.instant_move_card import InstantMoveCard


class Entropy(StatusEffect):
    """At the start of your turn, Transform `amount` cards in your Hand.

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
        from ...Registry.card_registry import transform_card_ids

        if event is not GameEvent.TURN_START:
            return None
        if context.target is not context.source:
            return None
        ally = context.source

        # `amount` cards, one question at a time. Each turns into a card of
        # its own pool (transform_card_ids): a Wound into another Status.
        def ask(left):
            if left <= 0 or not ally.hand:
                return
            def transform(chosen):
                ask(left - 1)
                options = transform_card_ids(chosen, solo=context.solo)
                effects = [InstantMoveCard(
                    source=ally, target=ally, card_ids=[chosen],
                    from_pile=InstantMoveCard.HAND,
                    to_pile=InstantMoveCard.GONE)]
                if options:
                    effects.append(InstantAddCard(
                        source=ally, target=ally,
                        card_id=context.rngs.card_selection.choice(options),
                        pile=InstantAddCard.HAND))
                return effects
            context.ask(ally, "Transform a card in your Hand",
                        lambda: list(ally.hand), transform)
        ask(self.amount)
        return None
