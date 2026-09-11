from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_damage import InstantDamage


class Juggernaut(StatusEffect):
    """Whenever you gain Block, deal damage to a random enemy."""

    def __init__(self, source, target, amount):
        super().__init__("juggernaut")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat

    def on_event(self, event, context):
        if event is not GameEvent.BLOCK_GAINED:
            return None
        if context.target is not context.source:
            return None
        alive = [e for e in context.all_enemies if e.is_alive()]
        if not alive:
            return None
        return [InstantDamage(
            source=context.source,
            target=context.rng.choice(alive),
            amount=self.amount,
        )]
