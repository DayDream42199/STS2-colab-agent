from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_damage import InstantDamage
from ..InstantEffects.instant_hp_loss import InstantHpLoss


class Inferno(StatusEffect):
    """At the start of your turn lose 1 HP; whenever you lose HP on your turn,
    deal damage to ALL enemies. The turn-start loss triggers the second half."""

    HP_LOSS = 1

    def __init__(self, source, target, amount):
        super().__init__("inferno")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat

    def on_event(self, event, context):
        if context.target is not context.source:
            return None

        if event is GameEvent.TURN_START:
            return [InstantHpLoss(
                source=context.source, target=context.source, amount=self.HP_LOSS)]

        if event is not GameEvent.HP_LOST:
            return None
        if context.payload.get("phase") != "PLAYER_TURN":
            return None
        return [
            InstantDamage(source=context.source, target=enemy, amount=self.amount)
            for enemy in context.all_enemies
            if enemy.is_alive()
        ]
