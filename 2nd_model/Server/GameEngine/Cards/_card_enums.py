from enum import Enum, auto

class CardType(Enum):
    ATTACK = auto()
    SKILL = auto()
    POWER = auto()
    CURSE = auto()
    QUEST = auto()
    STATUS = auto()

class CardClass(Enum):
    """Which pool a card belongs to. Orthogonal to CardRarity: a card has
    both, e.g. Coordinate is COLORLESS and UNCOMMON. STATUS, CURSE and TOKEN
    are pools too - cards that are never drafted, only handed to you."""
    IRONCLAD = auto()
    COLORLESS = auto()
    STATUS = auto()
    CURSE = auto()
    TOKEN = auto()

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