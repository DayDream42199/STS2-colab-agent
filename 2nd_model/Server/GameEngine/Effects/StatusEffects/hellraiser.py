from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_play_card import InstantPlayCard


class Hellraiser(StatusEffect):
    """Whenever you draw a card with "Strike" in its name, it is played
    against a random enemy.

    Reads the ids on CARD_DRAWN, so copies already in hand do not fire."""

    MATCH = "strike"

    def __init__(self, source, target, amount):
        super().__init__("hellraiser")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass

    def on_event(self, event, context):
        from ...Registry.card_registry import create_card

        if event is not GameEvent.CARD_DRAWN:
            return None
        if context.target is not context.source:
            return None
        living = [e for e in context.all_enemies if e.is_alive()]
        if not living:
            return None
        played = []
        for card_id in context.payload.get("card_ids", ()):
            if self.MATCH not in create_card(card_id).name.lower():
                continue
            played.append(InstantPlayCard(
                source=context.source, target=context.source,
                card_id=card_id, from_pile=InstantPlayCard.HAND,
                at=context.rng.choice(living)))
        return played or None
