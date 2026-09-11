from ._status_effect import StatusEffect


class TagTeam(StatusEffect):
    """Marks an enemy: the next Attack another player plays on it is played an
    extra time. Combat checks `source`, so the applier gets nothing."""

    IS_DEBUFF = True

    def __init__(self, source, target, amount):
        super().__init__("tag_team")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # waits for the teammate's attack, however long that takes
