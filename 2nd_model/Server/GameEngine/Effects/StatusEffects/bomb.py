from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_damage import InstantDamage


class Bomb(StatusEffect):
    """Counts down to a detonation that hits every enemy.

    `amount` is the turns until the next one goes off. Each The Bomb played
    is its own countdown with its own damage (40, 50 upgraded), as the game's
    TheBombPower instances are: `fuses` holds [turns, damage] per bomb."""

    def __init__(self, source, target, amount, damage=40):
        super().__init__("bomb")
        self.source = source
        self.target = target
        self.amount = amount
        self.fuses = [[amount, damage]]

    def absorb(self, other):
        self.fuses.extend(other.fuses)
        self.amount = min(turns for turns, _ in self.fuses)

    def on_owner_turn_end(self):
        pass  # counted down in on_event, on the owner's own TURN_END

    def on_event(self, event, context):
        if event is not GameEvent.TURN_END:
            return None
        if context.target is not context.source or not self.fuses:
            return None
        effects = []
        for fuse in self.fuses:
            fuse[0] -= 1
            if fuse[0] <= 0:
                effects += [
                    InstantDamage(source=context.source, target=enemy,
                                  amount=fuse[1], is_attack=False)
                    for enemy in context.all_enemies
                    if enemy.is_alive()
                ]
        self.fuses = [fuse for fuse in self.fuses if fuse[0] > 0]
        self.amount = min((turns for turns, _ in self.fuses), default=0)
        return effects or None
