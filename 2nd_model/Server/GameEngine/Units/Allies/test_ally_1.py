from ._ally import Ally

class TestAlly1(Ally):
    Card1 = "Strike".lower()
    Card2 = "Defend".lower()
    Card3 = "Bash".lower()
    DEFAULT_MAX_HP = 75
    DEFAULT_HP_VARIANCE = 5
    DEFAULT_MAX_ENERGY = 3
    DEFAULT_DECK = [Card1] * 5 + [Card2] * 5 + [Card3] * 1