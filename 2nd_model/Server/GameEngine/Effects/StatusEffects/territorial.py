from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from .strength import Strength


class Territorial(StatusEffect):
    """At the end of every enemy turn, gain `amount` Strength (Byrdonis, 1).
    The game's TerritorialPower; a power, so it does not wear off."""

    def __init__(self, source, target, amount):
        super().__init__("territorial")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass

    def on_event(self, event, context):
        if event is not GameEvent.ENEMY_TURN_END:
            return None
        owner = context.source
        return [Strength(source=owner, target=owner, amount=self.amount)]
