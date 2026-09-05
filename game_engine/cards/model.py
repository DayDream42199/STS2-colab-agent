"""Card model: the enums, the rarity tables and the Card dataclass."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, List, Optional, Union
import copy

from ..entities import HAND_LIMIT
from ..statuses import StatusType, DEBUFF_STATUSES


class CardType(Enum):
    ATTACK = auto()
    SKILL = auto()
    POWER = auto()
    STATUS = auto()
    CURSE = auto()


UNPLAYABLE = 999


class TargetMode(Enum):
    SINGLE_ENEMY = auto()
    ALL_ENEMIES = auto()
    SELF = auto()
    ALLY = auto()
    SELF_OR_ALLY = auto()


_BASIC_CARDS = {"Strike", "Defend", "Bash"}


_COMMON_CARDS = {
    "Anger", "Armaments", "Blood Wall", "Body Slam", "Breakthrough", "Cinder",
    "Havoc", "Headbutt", "Iron Wave", "Molten Fist", "Perfected Strike",
    "Pommel Strike", "Setup Strike", "Shrug It Off", "Sword Boomerang",
    "Taunt", "Thunderclap", "Tremble", "True Grit", "Twin Strike",
}


_RARE_CARDS = {
    "Aggression", "Barricade", "Brand", "Cascade", "Conflagration",
    "Crimson Mantle", "Dark Embrace", "Demon Form", "Dominate", "Feed",
    "Fiend Fire", "Hellraiser", "Impervious", "Juggernaut", "Mangle",
    "Midnight", "Not Yet", "Offering", "One-Two Punch", "Pact's End",
    "Primal Force", "Pyre", "Stoke", "Tank", "Tear Asunder", "Thrash",
    "Unmovable",
}


_ANCIENT_CARDS = {"Break", "Corruption"}


_TOKEN_CARDS = {"Giant Rock"}


_COLORLESS_CARDS = {
    "Ultimate Defend", "Ultimate Strike", "Finesse", "Flash of Steel",
    "Dark Shackles", "Prowess", "Impatience", "Shockwave", "Mind Blast",
    "Dramatic Entrance", "Fisticuffs", "Omnislice", "Entrench", "Caltrops",
    "Eternal Armor", "Rend", "Master of Strategy", "Rally", "Beat Down",
    "Catastrophe", "Secret Weapon", "Secret Technique",
}


def rarity_for_card(name: str, card_type: "CardType" = None) -> str:
    if card_type == CardType.STATUS:
        return "Status"
    if card_type == CardType.CURSE:
        return "Curse"
    if name in _BASIC_CARDS:
        return "Basic"
    if name in _COMMON_CARDS:
        return "Common"
    if name in _RARE_CARDS:
        return "Rare"
    if name in _ANCIENT_CARDS:
        return "Ancient"
    if name in _TOKEN_CARDS:
        return "Token"
    if name in _COLORLESS_CARDS:
        return "Colorless"
    return "Uncommon"


@dataclass(eq=False)
class Card:
    """eq=False: dataclass's default auto-generated __eq__ compares ALL fields, so two freshly-made..."""
    name: str
    cost: Union[int, str]
    card_type: CardType
    target: TargetMode
    effect: Callable
    values: Dict[str, int] = field(default_factory=dict)
    upgrade_values: Dict[str, int] = field(default_factory=dict)
    exhausts: bool = False
    loses_exhaust_on_upgrade: bool = False
    upgraded: bool = False
    is_multiplayer: bool = False
    upgrade_cost: Optional[int] = None
    combat_bonus_damage: int = 0
    rarity: str = ""
    description: str = ""
    upgraded_description: str = ""
    innate: bool = False
    innate_on_upgrade: bool = False
    dynamic_cost: Optional[Callable] = None
    temp_cost: Optional[int] = None
    replay: int = 0
    bound: bool = False
    retain: bool = False
    retain_on_upgrade: bool = False
    ethereal: bool = False
    loses_ethereal_on_upgrade: bool = False
    eternal: bool = False
    playable_if: Optional[Callable] = None

    def __post_init__(self):
        if not self.rarity:
            self.rarity = rarity_for_card(self.name, self.card_type)

    def val(self, key: str, default: int = 0) -> int:
        """Read a numeric value, honoring upgrade state."""
        if self.upgraded and key in self.upgrade_values:
            return self.upgrade_values[key]
        return self.values.get(key, default)

    def current_cost(self, player=None) -> Union[int, str]:
        """Read effective energy cost, honoring upgrade state and -- when a player is supplied -- combat state."""
        base = self.cost
        if self.upgraded and self.upgrade_cost is not None:
            base = self.upgrade_cost
        if player is None or base == "X":
            return base
        if self.dynamic_cost is not None:
            base = self.dynamic_cost(self, player)
        if self.temp_cost is not None:
            base = self.temp_cost
        if self.card_type == CardType.ATTACK and player.get_status(StatusType.TANGLED) > 0:
            base += 1
        if self.card_type == CardType.SKILL and player.skills_cost_zero:
            base = 0
        if self.card_type == CardType.ATTACK and player.next_attack_free:
            base = 0
        return max(0, base)

    def is_innate(self) -> bool:
        return self.innate or (self.upgraded and self.innate_on_upgrade)

    def upgrade(self):
        self.upgraded = True

    def clone(self) -> "Card":
        """An independent copy, for cards that add a copy of themselves (Anger, Outrage). copy.copy() alone..."""
        twin = copy.copy(self)
        twin.values = dict(self.values)
        twin.upgrade_values = dict(self.upgrade_values)
        return twin

    def exhausts_now(self) -> bool:
        """Whether THIS printing (base or upgraded) exhausts."""
        if self.upgraded and self.loses_exhaust_on_upgrade:
            return False
        return self.exhausts

    def retains_now(self) -> bool:
        """Whether THIS printing has Retain."""
        return self.retain or (self.upgraded and self.retain_on_upgrade)

    def is_ethereal(self) -> bool:
        """Whether THIS printing has Ethereal."""
        if self.upgraded and self.loses_ethereal_on_upgrade:
            return False
        return self.ethereal

    def is_unplayable(self) -> bool:
        """Statuses and Curses whose text is '$Unplayable'."""
        return self.cost == UNPLAYABLE

    def current_description(self) -> str:
        if self.upgraded and self.upgraded_description:
            return self.upgraded_description
        return self.description

    def __repr__(self):
        current = self.current_cost()
        cost_str = "X" if current == "X" else str(current)
        name = self.name + "+" if self.upgraded else self.name
        return f"<Card {name} ({cost_str})>"
