"""Status effect definitions for the combat replica."""

from enum import Enum, auto
from typing import Dict, Tuple


class StatusType(Enum):
    __hash__ = object.__hash__

    VULNERABLE = auto()
    WEAK = auto()
    FRAIL = auto()
    POISON = auto()
    SHRINK = auto()
    CONSTRICT = auto()

    STRENGTH = auto()
    STRENGTH_THIS_TURN = auto()
    DEXTERITY = auto()
    DEXTERITY_THIS_TURN = auto()
    RITUAL = auto()
    METALLICIZE = auto()
    PLATED_ARMOR = auto()
    REGEN = auto()
    SLIPPERY = auto()
    ARTIFACT = auto()
    SKITTISH = auto()
    THORNS = auto()
    THORNS_THIS_TURN = auto()
    VIGOR = auto()
    INTANGIBLE = auto()
    RINGING = auto()
    SMOGGY = auto()
    STRENGTH_LOSS = auto()
    DEXTERITY_LOSS = auto()
    STEAM_ERUPTION = auto()
    PERSONAL_HIVE = auto()
    RAVENOUS = auto()
    SUCK = auto()
    BUFFER = auto()
    DEXTERITY_LOSS_THIS_TURN = auto()
    TENDER = auto()
    BURROWED = auto()
    FLUTTER = auto()
    SOAR = auto()
    HEX = auto()
    DOWNGRADED = auto()
    SANDPIT = auto()
    PLOW = auto()
    STRENGTH_LOSS_THIS_TURN = auto()

    TANK_SELF = auto()
    TANK_ALLY = auto()

    LINKED = auto()

    TANGLED = auto()


class StackType(Enum):
    INTENSITY = auto()
    DURATION = auto()
    COUNTER = auto()
    NONSTACKING = auto()


class TurnBehavior(Enum):
    PERMANENT = auto()
    CONSERVED = auto()
    DECREMENTED = auto()
    REMOVED = auto()
    CONSUMED = auto()
    RESET = auto()


STATUS_META: Dict[StatusType, Tuple[StackType, TurnBehavior]] = {
    StatusType.VULNERABLE: (StackType.DURATION, TurnBehavior.DECREMENTED),
    StatusType.WEAK: (StackType.DURATION, TurnBehavior.DECREMENTED),
    StatusType.FRAIL: (StackType.DURATION, TurnBehavior.DECREMENTED),
    StatusType.POISON: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.SHRINK: (StackType.DURATION, TurnBehavior.DECREMENTED),
    StatusType.CONSTRICT: (StackType.INTENSITY, TurnBehavior.CONSERVED),
    StatusType.STRENGTH: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.STRENGTH_THIS_TURN: (StackType.INTENSITY, TurnBehavior.REMOVED),
    StatusType.DEXTERITY: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.DEXTERITY_THIS_TURN: (StackType.INTENSITY, TurnBehavior.REMOVED),
    StatusType.RITUAL: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.METALLICIZE: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.PLATED_ARMOR: (StackType.INTENSITY, TurnBehavior.DECREMENTED),
    StatusType.REGEN: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.SLIPPERY: (StackType.COUNTER, TurnBehavior.CONSUMED),
    StatusType.ARTIFACT: (StackType.COUNTER, TurnBehavior.CONSERVED),
    StatusType.SKITTISH: (StackType.COUNTER, TurnBehavior.PERMANENT),
    StatusType.THORNS: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.THORNS_THIS_TURN: (StackType.INTENSITY, TurnBehavior.REMOVED),
    StatusType.STRENGTH_LOSS_THIS_TURN: (StackType.INTENSITY, TurnBehavior.REMOVED),
    StatusType.VIGOR: (StackType.INTENSITY, TurnBehavior.CONSERVED),
    StatusType.INTANGIBLE: (StackType.DURATION, TurnBehavior.DECREMENTED),
    StatusType.RINGING: (StackType.DURATION, TurnBehavior.DECREMENTED),
    StatusType.SMOGGY: (StackType.DURATION, TurnBehavior.DECREMENTED),
    StatusType.STRENGTH_LOSS: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.DEXTERITY_LOSS: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.STEAM_ERUPTION: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.PERSONAL_HIVE: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.RAVENOUS: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.SUCK: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.PLOW: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.BUFFER: (StackType.COUNTER, TurnBehavior.CONSERVED),
    StatusType.DEXTERITY_LOSS_THIS_TURN: (StackType.INTENSITY, TurnBehavior.REMOVED),
    StatusType.TENDER: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.BURROWED: (StackType.NONSTACKING, TurnBehavior.PERMANENT),
    StatusType.FLUTTER: (StackType.COUNTER, TurnBehavior.CONSERVED),
    StatusType.SANDPIT: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.SOAR: (StackType.NONSTACKING, TurnBehavior.PERMANENT),
    StatusType.HEX: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.DOWNGRADED: (StackType.NONSTACKING, TurnBehavior.PERMANENT),
    StatusType.TANK_SELF: (StackType.NONSTACKING, TurnBehavior.PERMANENT),
    StatusType.TANK_ALLY: (StackType.NONSTACKING, TurnBehavior.PERMANENT),
    StatusType.LINKED: (StackType.NONSTACKING, TurnBehavior.REMOVED),
    StatusType.TANGLED: (StackType.DURATION, TurnBehavior.DECREMENTED),
}


DEBUFF_STATUSES = frozenset({
    StatusType.VULNERABLE,
    StatusType.WEAK,
    StatusType.FRAIL,
    StatusType.POISON,
    StatusType.SHRINK,
    StatusType.CONSTRICT,
    StatusType.TANGLED,
    StatusType.RINGING,
    StatusType.SMOGGY,
    StatusType.STRENGTH_LOSS,
    StatusType.DEXTERITY_LOSS,
    StatusType.STRENGTH_LOSS_THIS_TURN,
    StatusType.DEXTERITY_LOSS_THIS_TURN,
    StatusType.TENDER,
    StatusType.SANDPIT,
    StatusType.HEX,
    StatusType.DOWNGRADED,
})


def net_strength(statuses: dict) -> int:
    """Effective Strength: the number the rules actually use."""
    return (statuses.get(StatusType.STRENGTH, 0)
            + statuses.get(StatusType.STRENGTH_THIS_TURN, 0)
            - statuses.get(StatusType.STRENGTH_LOSS, 0)
            - statuses.get(StatusType.STRENGTH_LOSS_THIS_TURN, 0))


def net_dexterity(statuses: dict) -> int:
    """Effective Dexterity, the exact mirror of net_strength()."""
    return (statuses.get(StatusType.DEXTERITY, 0)
            + statuses.get(StatusType.DEXTERITY_THIS_TURN, 0)
            - statuses.get(StatusType.DEXTERITY_LOSS, 0)
            - statuses.get(StatusType.DEXTERITY_LOSS_THIS_TURN, 0))


def damage_multiplier_for_attacker(statuses: dict) -> float:
    """Multiplier applied to outgoing attack damage based on the attacker's own statuses."""
    mult = 1.0
    if statuses.get(StatusType.WEAK, 0) > 0:
        mult *= 0.75
    if statuses.get(StatusType.SHRINK, 0) > 0:
        mult *= 0.7
    return mult


def damage_multiplier_for_defender(statuses: dict, vulnerable_bonus: float = 0.0) -> float:
    """Multiplier applied to incoming attack damage based on the defender's own statuses."""
    mult = 1.0
    if statuses.get(StatusType.VULNERABLE, 0) > 0:
        mult *= 1.5 + vulnerable_bonus
    if statuses.get(StatusType.TANK_SELF, 0) > 0:
        mult *= 1.5
    if statuses.get(StatusType.TANK_ALLY, 0) > 0:
        mult *= 0.5
    return mult


def block_multiplier(statuses: dict) -> float:
    mult = 1.0
    if statuses.get(StatusType.FRAIL, 0) > 0:
        mult *= 0.75
    return mult
