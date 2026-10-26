from ._ally import Ally

class Ironclad(Ally):
    """The game's Ironclad (Models.Characters.Ironclad): 80 HP, no roll, 3
    energy, and its starting deck. Burning Blood, the starting relic, heals
    after a fight, so it does nothing inside one and is left out."""
    DEFAULT_MAX_HP = 80
    DEFAULT_HP_VARIANCE = 0
    DEFAULT_MAX_ENERGY = 3
    DEFAULT_DECK = ["strike"] * 5 + ["defend"] * 4 + ["bash"]
