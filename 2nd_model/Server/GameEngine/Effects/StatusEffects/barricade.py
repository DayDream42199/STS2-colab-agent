from ._status_effect import StatusEffect


class Barricade(StatusEffect):
    """Block is not removed at the start of your turn.

    clear_block asks every status, so this needs no hook in Combat."""

    def __init__(self, source, target, amount):
        super().__init__("barricade")
        self.source = source
        self.target = target
        self.amount = amount

    def keeps_block(self):
        return True

    def on_owner_turn_end(self):
        pass
