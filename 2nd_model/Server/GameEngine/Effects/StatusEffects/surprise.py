from ._status_effect import StatusEffect


class Surprise(StatusEffect):
    """Gremlin Merc: when it dies, a Sneaky Gremlin and a Fat Gremlin jump in
    (its on_death calls them). Carried so the players can see it coming, as
    the game shows its SurprisePower."""

    def __init__(self, source, target, amount=1):
        super().__init__("surprise")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass
