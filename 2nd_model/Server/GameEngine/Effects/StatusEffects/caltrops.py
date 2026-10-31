from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_damage import InstantDamage


class Caltrops(StatusEffect):
    """Whenever you are attacked, deal damage back. Unlike Flame Barrier this
    is a Power: it lasts the whole combat rather than one turn. The game's
    ThornsPower - Toadpole's Thorns too. The damage back is unpowered: no
    Strength on it, and it is nobody's attack, so it sets off no Thorns."""

    def __init__(self, source, target, amount):
        super().__init__("caltrops")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # a power lasts the whole combat

    def on_event(self, event, context):
        if event is not GameEvent.ATTACKED:
            return None
        if context.target is not context.source:
            return None
        attacker = context.payload.get("attacker")
        if attacker is None or not attacker.is_alive() or self.amount <= 0:
            return None
        return [InstantDamage(
            source=context.source, target=attacker, amount=self.amount, is_attack=False)]
