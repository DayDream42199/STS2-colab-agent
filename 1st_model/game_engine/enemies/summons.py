"""Enemies that only ever arrive mid-fight, spawned by another."""

from typing import List, Callable, Optional
import random

from ..entities import Entity, CONTENT_RNG
from ..statuses import StatusType
from ..cards import (make_wound, make_dazed, make_burn, make_slimed,
                     make_infection, make_beckon, make_toxic,
                     make_wither, make_frantic_escape)
from .model import (Enemy, IntentType, Move, ACT_SCALING,
                    SPECIAL_BUFF_STATUSES, hp_scale_multiplier,
                    block_scale_multiplier, scale_enemy_for_players,
                    scale_special_buff)
from .shared import *  # noqa: F401,F403
from .shared import (_bowlbug, _dmg_move, _make_battle_friend,
                     _make_cultist, _multi_hit, _nothing,
                     _shuffle_status_cards)


def make_eye_with_teeth() -> Enemy:
    """Wiki: Minion, HP 6."""
    def _distract(engine, enemy):
        target = engine.pick_enemy_attack_target()
        _shuffle_status_cards(engine, target, make_dazed, 3, "Dazed")
    distract = Move("Distract", IntentType.DEBUFF, _distract, damage=0)
    e = Enemy("Eye With Teeth", 6, [distract], lambda en, t: distract)
    e.is_minion = True
    return e


def make_fat_gremlin() -> Enemy:
    """Wiki: Minion, HP 13-17."""
    spawned = Move("Spawned", IntentType.BUFF, _nothing, damage=0)

    def _flee(engine, enemy):
        enemy.alive = False
        enemy.death_resolved = True
        engine.log.append(f"{enemy.name} flees from combat")
    flee = Move("Flee", IntentType.BUFF, _flee, damage=0)

    def choose(enemy: Enemy, turn: int) -> Move:
        return spawned if turn == 0 else flee

    e = Enemy("Fat Gremlin", CONTENT_RNG.randint(13, 17), [spawned, flee], choose)
    e.is_minion = True
    return e


def make_sneaky_gremlin() -> Enemy:
    """Wiki: Minion, HP 10-14. Spawned (does nothing); Tackle (9 dmg)."""
    spawned = Move("Spawned", IntentType.BUFF, _nothing, damage=0)
    tackle = Move("Tackle", IntentType.ATTACK, _dmg_move(9), damage=9)

    def choose(enemy: Enemy, turn: int) -> Move:
        return spawned if turn == 0 else tackle

    e = Enemy("Sneaky Gremlin", CONTENT_RNG.randint(10, 14), [spawned, tackle], choose)
    e.is_minion = True
    return e


def make_gas_bomb() -> Enemy:
    """Wiki: Minion, HP 7."""
    def _explode(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(8), log=engine.log,
                            label=enemy.name, attacker=enemy)
        enemy.alive = False
        enemy.death_resolved = True
        engine.log.append(f"{enemy.name} explodes and dies")
    explode = Move("Explode", IntentType.ATTACK, _explode, damage=8)
    e = Enemy("Gas Bomb", 7, [explode], lambda en, t: explode)
    e.is_minion = True
    return e


def make_hatchling() -> Enemy:
    """What a Tough Egg becomes."""
    nibble = Move("Nibble", IntentType.ATTACK, _dmg_move(6), damage=6)
    e = Enemy("Hatchling", CONTENT_RNG.randint(19, 22), [nibble], lambda en, t: nibble)
    e.is_minion = True
    return e


def make_tough_egg() -> Enemy:
    """Wiki: Minion, HP 14-18."""
    def _hatch(engine, enemy):
        engine.summon_enemy(make_hatchling(), summoner=enemy)
        enemy.alive = False
        enemy.death_resolved = True
        engine.log.append(f"{enemy.name} hatches")
    hatch = Move("Hatch", IntentType.BUFF, _hatch, damage=0)
    nibble = Move("Nibble", IntentType.ATTACK, _dmg_move(4), damage=4)

    def choose(enemy: Enemy, turn: int) -> Move:
        return nibble if turn == 0 else hatch

    e = Enemy("Tough Egg", CONTENT_RNG.randint(14, 18), [nibble, hatch], choose)
    e.is_minion = True
    return e


def make_parafright() -> Enemy:
    """Wiki: Minion, HP 21. Slam (16 dmg). Summoned by The Obscura."""
    slam = Move("Slam", IntentType.ATTACK, _dmg_move(16), damage=16)
    e = Enemy("Parafright", 21, [slam], lambda en, t: slam)
    e.is_minion = True
    return e


def make_zapbot() -> Enemy:
    """Wiki: Minion, HP 18-23. Zap (14 dmg). Built by the Fabricator."""
    zap = Move("Zap", IntentType.ATTACK, _dmg_move(14), damage=14)
    e = Enemy("Zapbot", CONTENT_RNG.randint(18, 23), [zap], lambda en, t: zap)
    e.is_minion = True
    return e


def make_stabbot() -> Enemy:
    """Wiki: Minion, HP 18-23. Stab (11 dmg, applies 1 Frail)."""
    def _frail_rider(engine, enemy, target):
        target.add_status(StatusType.FRAIL, 1, applier=enemy)
    stab = Move("Stab", IntentType.ATTACK, _multi_hit(11, 1, _frail_rider), damage=11)
    e = Enemy("Stabbot", CONTENT_RNG.randint(18, 23), [stab], lambda en, t: stab)
    e.is_minion = True
    return e


def make_guardbot() -> Enemy:
    """Wiki: Minion, HP 16-20."""
    def _guard(engine, enemy):
        fab = next((e for e in engine.enemies_alive() if e.name == "Fabricator"), None)
        if fab is None:
            fab = enemy.leader if (enemy.leader and enemy.leader.alive) else None
        if fab is None:
            others = [e for e in engine.enemies_alive() if e is not enemy]
            fab = others[0] if others else enemy
        fab.gain_block(15)
        engine.log.append(f"{enemy.name} gives {fab.name} 15 Block")
    guard = Move("Guard", IntentType.DEFEND, _guard, damage=0)
    e = Enemy("Guardbot", CONTENT_RNG.randint(16, 20), [guard], lambda en, t: guard)
    e.is_minion = True
    return e


def make_noisebot() -> Enemy:
    """Wiki: Minion, HP 18-23."""
    def _noise(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.draw_pile.insert(0, make_dazed())
        target.discard_pile.append(make_dazed())
        engine.log.append(f"{target.name} gains 2 Dazed (1 draw pile, 1 discard)")
    noise = Move("Noise", IntentType.DEBUFF, _noise, damage=0)
    e = Enemy("Noisebot", CONTENT_RNG.randint(18, 23), [noise], lambda en, t: noise)
    e.is_minion = True
    return e
