from ._status_effect import StatusEffect


class Minion(StatusEffect):
    """Belongs to another enemy, and leaves the fight when that leader dies
    (Eye With Teeth to Fogmog). Combat reads it when it resolves a death; the
    leader itself is `enemy.leader`, set when the minion is summoned."""

    def __init__(self, source, target, amount=1):
        super().__init__("minion")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass
