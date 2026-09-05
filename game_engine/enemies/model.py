"""The Enemy model: intents, moves, and the multiplayer scaling rules."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Callable, Optional
import random

from ..entities import Entity, CONTENT_RNG
from ..statuses import StatusType


class IntentType(Enum):
    ATTACK = auto()
    ATTACK_DEBUFF = auto()
    DEFEND = auto()
    BUFF = auto()
    DEBUFF = auto()


ACT_SCALING = {"act1": 1.1, "act2": 1.2, "act3": 1.2, "act3boss": 1.3}


def hp_scale_multiplier(player_count: int, act: str = "act1") -> float:
    if player_count <= 1:
        return 1.0
    return player_count * ACT_SCALING.get(act, 1.0)


def block_scale_multiplier(player_count: int, act: str = "act1") -> float:
    if player_count <= 1:
        return 1.0
    if player_count == 2:
        return 2.0
    return player_count * ACT_SCALING.get(act, 1.0)


def scale_special_buff(status_name: str, base_amount: float, player_count: int) -> float:
    """Formulas confirmed on the wiki for enemy buffs that scale differently than plain HP/Block."""
    if player_count <= 1:
        return base_amount
    n = player_count
    if status_name == "plating":
        return base_amount * ((n - 1) * 2 + 1)
    if status_name == "artifact":
        return base_amount + (n - 1)
    if status_name == "slippery":
        return base_amount * n
    if status_name == "skittish":
        return int(base_amount * ((n - 1) * 0.5 + 1))
    return base_amount * hp_scale_multiplier(player_count)


SPECIAL_BUFF_STATUSES = {
    StatusType.PLATED_ARMOR: "plating",
    StatusType.SLIPPERY: "slippery",
    StatusType.ARTIFACT: "artifact",
    StatusType.SKITTISH: "skittish",
}


def scale_enemy_for_players(enemy: "Enemy", player_count: int, act: str = "act1") -> "Enemy":
    """Apply real STS2 multiplayer HP + Block scaling in place, plus any special-buff scaling for..."""
    if getattr(enemy, "_scaled_for_players", False):
        return enemy
    enemy._scaled_for_players = True
    hp_mult = hp_scale_multiplier(player_count, act)
    if hp_mult != 1.0:
        scaled = max(1, round(enemy.max_hp * hp_mult))
        enemy.max_hp = scaled
        enemy.hp = scaled
    enemy.block_scale_mult = block_scale_multiplier(player_count, act)
    for status, name in SPECIAL_BUFF_STATUSES.items():
        base = enemy.get_status(status)
        if base > 0:
            enemy.statuses[status] = round(scale_special_buff(name, base, player_count))
    return enemy


@dataclass
class Move:
    name: str
    intent: IntentType
    resolve: Callable
    damage: int = 0


class Enemy(Entity):
    def __init__(self, name: str, max_hp: int, moveset: List[Move],
                 choose_move: Callable[["Enemy", int], Move],
                 category: str = "normal"):
        super().__init__(name, max_hp)
        self.moveset = moveset
        self._choose_move = choose_move
        self.current_move: Optional[Move] = None
        self.turn_count = 0
        self.rng = random.Random()
        self.block_scale_mult = 1.0
        self.category = category
        self.hit_by_current_card = False
        self.skittish_used_this_turn = False
        self.on_death: Optional[Callable] = None
        self.death_resolved = False
        self.is_minion = False
        self.leader: Optional["Enemy"] = None
        self.stunned_turns = 0
        self.revive_in = 0
        self.on_revive: Optional[Callable] = None
        self.invulnerable = False
        self.attacked_by_this_turn = []
        self.knockdown = None

    def gain_block(self, amount: int, from_card: bool = True):
        """Overrides Entity.gain_block to apply real STS2 multiplayer block scaling (see..."""
        return super().gain_block(amount * self.block_scale_mult, from_card)

    def start_combat(self, seed: Optional[int] = None):
        if seed is not None:
            self.rng.seed(seed)
        self.turn_count = 0
        self.current_move = self._choose_move(self, self.turn_count)

    def queue_next_move(self):
        self.turn_count += 1
        self.current_move = self._choose_move(self, self.turn_count)

    def take_turn(self, engine):
        """Mirrors Player.start_turn()/end_turn()'s status bookkeeping around the enemy's action."""
        if not self.has_status(StatusType.BURROWED):
            self.block = 0
        self.skittish_used_this_turn = False
        self.tick_start_of_turn(engine.log)
        if not self.alive:
            return

        if self.current_move is None:
            self.current_move = self._choose_move(self, self.turn_count)
        engine.log.append(f"{self.name} uses {self.current_move.name}")
        self.current_move.resolve(engine, self)
        self.queue_next_move()

        self.apply_end_of_turn_gains(engine.log)
        self.decay_statuses_end_of_turn()
