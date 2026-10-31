from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from .strength import Strength


class Suck(StatusEffect):
    """After each of its attacks, `amount` Strength for every hit that got
    through someone's Block (Fossil Stalker, 3) - per hit, however many
    players it reached. The game's SuckPower, which grants it once the
    attack is over, so a hit never feeds the next hit of the same attack;
    here it is paid when the enemies' turn ends, which comes to the same."""

    def __init__(self, source, target, amount):
        super().__init__("suck")
        self.source = source
        self.target = target
        self.amount = amount
        self._hits = set()

    def on_owner_turn_end(self):
        pass

    def on_event(self, event, context):
        owner = context.source
        if event is GameEvent.ATTACKED:
            payload = context.payload
            if payload.get("attacker") is owner and payload.get("amount", 0) > 0:
                self._hits.add(payload.get("hit"))
            return None
        if event is GameEvent.ENEMY_TURN_END and self._hits:
            gained = self.amount * len(self._hits)
            self._hits = set()
            return [Strength(source=owner, target=owner, amount=gained)]
        return None
