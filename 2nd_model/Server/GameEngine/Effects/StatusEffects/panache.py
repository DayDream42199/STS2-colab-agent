from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_damage import InstantDamage


class Panache(StatusEffect):
    """Every Nth card played in a single turn, hit the whole board."""

    EVERY = 5
    DAMAGE = 10

    def __init__(self, source, target, amount):
        super().__init__("panache")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat

    def on_event(self, event, context):
        if event is not GameEvent.CARD_PLAYED:
            return None
        if context.target is not context.source:
            return None
        played = context.source.turn_count("cards_played")
        if played == 0 or played % self.EVERY != 0:
            return None
        return [
            InstantDamage(source=context.source, target=enemy, amount=self.DAMAGE)
            for enemy in context.all_enemies
            if enemy.is_alive()
        ]
