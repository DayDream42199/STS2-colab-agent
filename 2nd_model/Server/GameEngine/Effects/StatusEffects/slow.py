from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent


class Slow(StatusEffect):
    """Attacks on the holder deal 10% more for every card played this turn,
    by anyone; the count starts again when the enemies' turn begins (Bygone
    Effigy). `amount` is that count - the game shows it as a percentage, ten
    times as much. A debuff in the game, and it does not wear off."""

    IS_DEBUFF = True
    ATTACKS_ONLY = True                 # the game's IsPoweredAttack
    DAMAGE_ORDER = StatusEffect.MULTIPLICATIVE
    PER_CARD = 0.1

    def __init__(self, source, target, amount=0):
        super().__init__("slow")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass

    def is_expired(self):
        return False                    # a count that falls to 0, not a duration

    def on_event(self, event, context):
        if event is GameEvent.CARD_PLAYED:
            self.amount += 1
        elif event is GameEvent.ENEMY_TURN_START:
            self.amount = 0
        return None

    def modify_incoming_damage(self, amount, attacker=None):
        return amount * (1 + self.PER_CARD * self.amount)
