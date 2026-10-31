from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent


class HardenedShell(StatusEffect):
    """Skulking Colony. It loses at most `amount` HP a turn, whoever's turn:
    what gets through Block past that is not lost. The count starts again
    at the start of every turn, the players' and the enemies'. The game's
    HardenedShellPower; a power, it does not wear off."""

    def __init__(self, source, target, amount):
        super().__init__("hardened_shell")
        self.source = source
        self.target = target
        self.amount = amount
        self.lost_this_turn = 0

    def on_owner_turn_end(self):
        pass

    def modify_hp_lost(self, amount):
        if amount <= 0:
            return amount
        amount = min(amount, max(0, self.amount - self.lost_this_turn))
        self.lost_this_turn += amount
        return amount

    def on_event(self, event, context):
        if event in (GameEvent.TURN_START, GameEvent.ENEMY_TURN_START):
            self.lost_this_turn = 0
        return None
