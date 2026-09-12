from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent


class ColossusGuard(StatusEffect):
    """Take half damage from Vulnerable attackers.

    Clears on the owner's next TURN_START, not the end-of-turn tick, which
    runs before the enemy phase."""

    ATTACKS_ONLY = True
    REDUCTION = 0.5
    DAMAGE_ORDER = StatusEffect.MULTIPLICATIVE

    def __init__(self, source, target, amount):
        super().__init__("colossus_guard")
        self.source = source
        self.target = target
        self.amount = amount

    def modify_incoming_damage(self, amount, attacker=None):
        if self.amount <= 0 or attacker is None:
            return amount
        if not attacker.get_status("vulnerable"):
            return amount
        return amount * self.REDUCTION

    def on_owner_turn_end(self):
        pass  # survives into the enemy phase

    def on_event(self, event, context):
        if event is GameEvent.TURN_START and context.target is context.source:
            self.amount -= 1
        return None
