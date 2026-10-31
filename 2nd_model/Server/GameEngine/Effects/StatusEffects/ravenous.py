from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from .strength import Strength
from .stun import Stun


class Ravenous(StatusEffect):
    """When another enemy dies, devour it: stunned for a turn - the move it had
    lined up comes the turn after - and `amount` Strength (Corpse Slug, 4).
    The game's RavenousPower; a power, it does not wear off."""

    def __init__(self, source, target, amount):
        super().__init__("ravenous")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass

    def on_event(self, event, context):
        owner, dead = context.source, context.target
        if event is not GameEvent.ENEMY_DIED or dead is owner or not owner.is_alive():
            return None
        if dead not in context.all_enemies or owner not in context.all_enemies:
            return None
        return [Stun(source=owner, target=owner, amount=1),
                Strength(source=owner, target=owner, amount=self.amount)]
