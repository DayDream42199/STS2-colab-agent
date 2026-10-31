from ._status_effect import StatusEffect


class SteamEruption(StatusEffect):
    """Waterfall Giant's pressure, built up move by move. Does nothing of
    its own: the giant's on_death reads it - brought down while holding it,
    it does not die but blows, for this much. The game's SteamEruptionPower;
    a buff, not scaled for the party."""

    def __init__(self, source, target, amount):
        super().__init__("steam_eruption")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass
