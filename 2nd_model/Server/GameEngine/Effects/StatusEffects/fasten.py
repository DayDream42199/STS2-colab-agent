from ._status_effect import StatusEffect


class Fasten(StatusEffect):
    """Defend cards (Defend, Ultimate Defend) give `amount` more Block.

    Read by Card.base_block, which adds it to the card's own Block before
    Dexterity and Frail - one gain, as the game's FastenPower does with
    ModifyBlockAdditive. It used to grant a second Block after the card was
    played, so Dexterity counted twice and Unmovable doubled only one half.
    A power: lasts the whole combat."""

    def __init__(self, source, target, amount):
        super().__init__("fasten")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass
