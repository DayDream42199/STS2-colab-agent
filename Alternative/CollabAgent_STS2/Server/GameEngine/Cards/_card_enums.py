from enum import Enum, auto

class CardType(Enum):
    ATTACK = auto()
    SKILL = auto()
    POWER = auto()
    CURSE = auto()
    QUEST = auto()
    STATUS = auto()

class CardClass(Enum):
    """Which character's pool a card belongs to. Orthogonal to CardRarity:
    a card has both, e.g. Coordinate is COLORLESS and UNCOMMON. Add further
    characters here as they are implemented."""
    IRONCLAD = auto()
    COLORLESS = auto()

class CardRarity(Enum):
    BASIC = auto()
    COMMON = auto()
    UNCOMMON = auto()
    RARE = auto()
    ANCIENT = auto()

class TargetType(Enum):
    ENEMY = auto()
    ALL_ENEMIES = auto()
    RANDOM_ENEMY = auto()
    SELF = auto()
    ALLY = auto()
    ALL_ALLIES = auto()
    RANDOM_ALLY = auto()