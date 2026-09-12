from ._status_effect import StatusEffect


class Infested(StatusEffect):
    """When this dies, `amount` Wrigglers burst out of it (Phrog Parasite, 4).

    Carried as a status so the players can see it coming; the Parasite's
    on_death reads the number off it."""

    def __init__(self, source, target, amount):
        super().__init__("infested")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass
