from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent


class Vigor(StatusEffect):
    """Adds to the damage of the next attack, then is spent.

    Every hit of that attack, on every target, as the game's VigorPower:
    Twin Strike gets it twice, an enemy's attack lands it on each player.
    Spent once the attack is over - a card's when its play ends, an enemy's
    when the enemies' turn does. Reading the bonus spends nothing - an intent
    or Thrash may ask."""

    DAMAGE_ORDER = StatusEffect.ADDITIVE

    def __init__(self, source, target, amount):
        super().__init__("vigor")
        self.source = source
        self.target = target
        self.amount = amount
        self.in_use = False

    def modify_outgoing_damage(self, amount, target=None):
        if self.amount <= 0:
            return amount
        return amount + self.amount

    def after_attack_dealt(self):
        self.in_use = True  # spent once this attack is over

    def on_event(self, event, context):
        if not self.in_use:
            return None
        if ((event is GameEvent.CARD_PLAYED and context.target is context.source)
                or event is GameEvent.ENEMY_TURN_END):
            self.amount = 0  # spent; the next tick removes it
            self.in_use = False
        return None

    def on_owner_turn_end(self):
        pass
