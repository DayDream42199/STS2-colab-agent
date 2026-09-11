from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_damage import InstantDamage


class Bomb(StatusEffect):
    """Counts down to a detonation that hits every enemy.

    `amount` is turns remaining, so the damage is a class constant."""

    DAMAGE = 40

    def __init__(self, source, target, amount):
        super().__init__("bomb")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # counted down in on_event, on the owner's own TURN_END

    def on_event(self, event, context):
        if event is not GameEvent.TURN_END:
            return None
        if context.target is not context.source or self.amount <= 0:
            return None
        self.amount -= 1
        if self.amount > 0:
            return None
        return [
            InstantDamage(source=context.source, target=enemy,
                          amount=self.DAMAGE, is_attack=False)
            for enemy in context.all_enemies
            if enemy.is_alive()
        ]
