from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_add_card import InstantAddCard
from ...Cards._card_ref import CardRef


class WitheringPresence(StatusEffect):
    """Aeonglass's hold on one player: every 6 cards they play, a Wither goes
    straight into their hand, as upgraded as Aeonglass's Withers are by then.
    `amount` is the cards left to go, which is what the game shows.

    The game keeps one of these on the boss per player; here each player
    carries their own, with the boss as `source`. It ends with the boss."""

    CARDS = 6

    def __init__(self, source, target, amount=CARDS):
        super().__init__("withering_presence")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass

    def is_expired(self):
        return self.source is not None and not self.source.is_alive()

    def on_event(self, event, context):
        if event is not GameEvent.CARD_PLAYED or context.target is not context.source:
            return None
        if self.source is not None and not self.source.is_alive():
            return None
        self.amount -= 1
        if self.amount > 0:
            return None
        self.amount = self.CARDS
        level = getattr(self.source, "wither_upgrades", 0)
        return [InstantAddCard(
            source=self.source, target=context.source, pile=InstantAddCard.HAND,
            card_id=CardRef("wither", bonus_damage=3 * level))]
