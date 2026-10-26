from ._instant_effect import InstantEffect

class InstantBlock(InstantEffect):
    def __init__(self, source, target, amount, powered=True, card=True, play_id=None):
        super().__init__("instant_block")
        self.source = source
        self.target = target
        self.amount = amount
        # The game's ValueProp, in two flags. `powered` False: not a card's own
        # Block value (Entrench granting again what you hold) - Dexterity and
        # Frail skip it. `card` False: granted by a power on its own, not by a
        # card or an enemy's move (Toric Toughness's later turns) - Unmovable
        # skips it too, and Dexterity and Frail with it.
        self.powered = powered
        self.card = card
        # Which card play gave it - Combat stamps it, as the game's CardPlay
        # rides along with a block gain. Unmovable counts plays by it.
        self.play_id = play_id
