from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_damage import InstantDamage


class RollingBoulder(StatusEffect):
    """At the start of your turn, damage every enemy, then grow by 5.

    `amount` is the damage, not a duration, so it must never tick down. Each
    Rolling Boulder played rolls on its own and grows by 5 on its own, as the
    game's RollingBoulderPower instances do: `boulders` is their damage."""

    GROWTH = 5

    def __init__(self, source, target, amount):
        super().__init__("rolling_boulder")
        self.source = source
        self.target = target
        self.amount = amount
        self.boulders = [amount]

    def absorb(self, other):
        self.boulders.extend(other.boulders)
        self.amount = sum(self.boulders)

    def on_owner_turn_end(self):
        pass

    def on_event(self, event, context):
        if event is not GameEvent.TURN_START:
            return None
        if context.target is not context.source:
            return None
        effects = []
        for damage in self.boulders:
            effects += [
                InstantDamage(source=context.source, target=enemy,
                              amount=damage, is_attack=False)
                for enemy in context.all_enemies
                if enemy.is_alive()
            ]
        self.boulders = [damage + self.GROWTH for damage in self.boulders]
        self.amount = sum(self.boulders)
        return effects
