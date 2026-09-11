from ._ally import Ally

class TestAlly1(Ally):
    DEFAULT_MAX_HP = 75
    DEFAULT_HP_VARIANCE = 5
    DEFAULT_MAX_ENERGY = 3
    DEFAULT_DECK = ["strike"] * 5 + ["defend"] * 4 + ["bash"]