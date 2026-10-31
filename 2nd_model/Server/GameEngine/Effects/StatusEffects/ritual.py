from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from .strength import Strength


class Ritual(StatusEffect):
    """At the end of every enemy turn, gain `amount` Strength - but not the
    turn it was cast: the Cultists' Incantation pays from the turn after. The
    game's RitualPower (WasJustAppliedByEnemy); a power, it does not wear off."""

    def __init__(self, source, target, amount):
        super().__init__("ritual")
        self.source = source
        self.target = target
        self.amount = amount
        self.just_cast = True

    def on_owner_turn_end(self):
        pass

    def on_event(self, event, context):
        if event is not GameEvent.ENEMY_TURN_END:
            return None
        if self.just_cast:
            self.just_cast = False
            return None
        owner = context.source
        return [Strength(source=owner, target=owner, amount=self.amount)]
