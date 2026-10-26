from ._status_effect import StatusEffect


class Artifact(StatusEffect):
    """Cancels the next `amount` debuffs aimed at its holder, one charge each
    (Cubex Construct, Aeonglass). The resolver does the cancelling; this only
    carries the charges. In co-op the game gives one more per extra player."""

    def __init__(self, source, target, amount):
        super().__init__("artifact")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # charges, not a duration


def artifact_for(players, amount):
    """The game's co-op scaling for Artifact: +1 per player beyond the first."""
    return amount + max(0, players - 1)
