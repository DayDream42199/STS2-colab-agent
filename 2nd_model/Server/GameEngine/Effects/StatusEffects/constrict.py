from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_damage import InstantDamage


class Constrict(StatusEffect):
    """While the enemy that applied it is alive, take `amount` damage at the
    end of each of your turns (Slithering Strangler applies 3).

    The stacks never decay; killing the Strangler is the way out. Its damage
    is not an attack: Block stops it, Strength and Vulnerable do not touch it,
    and nothing that reacts to being attacked fires."""

    IS_DEBUFF = True

    def __init__(self, source, target, amount):
        super().__init__("constrict")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # intensity, not duration

    def on_event(self, event, context):
        if event is not GameEvent.TURN_END:
            return None
        if context.target is not context.source:       # somebody else's turn end
            return None
        if self.source is not None and not self.source.is_alive():
            return None
        return [InstantDamage(source=self.source, target=context.source,
                              amount=self.amount, is_attack=False)]

    def is_expired(self):
        # Kept as long as the Strangler lives; gone at the tick after it dies.
        return self.amount <= 0 or (self.source is not None and not self.source.is_alive())
