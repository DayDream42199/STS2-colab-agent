from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent


class Intangible(StatusEffect):
    """All incoming damage is reduced to 1.

    Applies last, after Strength and Vulnerable. Clears on the owner's next
    TURN_START, not the end-of-turn tick."""

    DAMAGE_ORDER = StatusEffect.MULTIPLICATIVE + 10

    def __init__(self, source, target, amount):
        super().__init__("intangible")
        self.source = source
        self.target = target
        self.amount = amount

    def modify_incoming_damage(self, amount, attacker=None):
        if self.amount <= 0:
            return amount
        return min(amount, 1)

    def on_owner_turn_end(self):
        pass  # survives into the enemy phase; see the class docstring

    def on_event(self, event, context):
        if context.source not in context.all_allies:
            # On an enemy (Soul Fysh's Fade) it counts down as the enemies'
            # turn ends - the game's AfterSideTurnEnd, enemy side - so 2 cover
            # the players' next turn and no more.
            if event is GameEvent.ENEMY_TURN_END:
                self.amount -= 1
            return None
        if event is not GameEvent.TURN_START:
            return None
        if context.target is not context.source:
            return None
        self.amount -= 1  # spent; the next tick removes it once it hits zero
        return None
