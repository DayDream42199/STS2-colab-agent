from ._status_effect import StatusEffect


class Illusion(StatusEffect):
    """Killed, it comes back at full HP the turn after (Eye With Teeth).

    Read by ScriptedEnemy.on_death: a dying enemy holding this schedules its
    own revival instead of staying down - unless its leader is already dead,
    in which case there is nobody left to cast it. Killing the Eye buys one
    Distract-free turn; killing Fogmog ends it."""

    def __init__(self, source, target, amount=1):
        super().__init__("illusion")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass
