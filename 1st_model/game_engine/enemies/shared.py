"""Move builders and enemy pieces reused across regions."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Callable, Optional
import random

from ..entities import Entity, CONTENT_RNG
from ..statuses import StatusType
from ..cards import (make_wound, make_dazed, make_burn,
                     make_slimed, make_infection, make_beckon,
                     make_toxic, make_wither,
                     make_frantic_escape)
from .model import (Enemy, IntentType, Move, ACT_SCALING,
                    SPECIAL_BUFF_STATUSES,
                    hp_scale_multiplier,
                    block_scale_multiplier,
                    scale_enemy_for_players,
                    scale_special_buff)


def _dmg_move(base):
    def _resolve(engine, enemy):
        dmg = enemy.deal_attack_damage(base)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
    return _resolve


def _shuffle_status_cards(engine, target, factory, count, label):
    for _ in range(count):
        target.discard_pile.append(factory())
    engine.log.append(f"{target.name} has {count} {label} shuffled into their discard pile")


def _make_cultist(name: str, hp_range, ritual_amount: int, strike_damage: int) -> Enemy:
    """Calcified and Damp Cultist share a moveset and differ only in numbers: Incantation (gain N..."""
    def _incantation(engine, enemy):
        enemy.add_status(StatusType.RITUAL, ritual_amount)
        engine.log.append(f"{enemy.name} gains {ritual_amount} Ritual")
    incantation = Move("Incantation", IntentType.BUFF, _incantation, damage=0)
    dark_strike = Move("Dark Strike", IntentType.ATTACK, _dmg_move(strike_damage),
                        damage=strike_damage)

    def choose(enemy: Enemy, turn: int) -> Move:
        return incantation if turn == 0 else dark_strike

    return Enemy(name, CONTENT_RNG.randint(*hp_range), [incantation, dark_strike], choose)


def _nothing(engine, enemy):
    """A move that does nothing (Sleep / Stun / Spawned)."""
    return


def _multi_hit(dmg, hits, extra=None):
    """N hits of the same damage, stopping early if the target dies, with an optional rider (apply..."""
    def _resolve(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(hits):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(dmg), log=engine.log,
                                label=enemy.name, attacker=enemy)
        if extra is not None:
            extra(engine, enemy, target)
    return _resolve


def _make_battle_friend(version: int, hp: int) -> Enemy:
    """Glory event encounter."""
    nothing = Move("Nothing", IntentType.BUFF, _nothing, damage=0)
    return Enemy(f"Battle Friend V{version}.0", hp, [nothing], lambda e, t: nothing)


def _bowlbug(name, hp_range, moves, choose):
    return Enemy(name, CONTENT_RNG.randint(*hp_range), moves, choose)
