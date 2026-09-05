"""Enemies that only appear from events."""

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
from .summons import *  # noqa: F401,F403  -- enemies these spawn
from .shared import *  # noqa: F401,F403
from .shared import (_bowlbug, _dmg_move, _make_battle_friend,
                     _make_cultist, _multi_hit, _nothing,
                     _shuffle_status_cards)


def make_the_merchant() -> Enemy:
    """Wiki: Event enemy, HP 165, from a Hive/Glory event encounter."""
    swipe = Move("Swipe", IntentType.ATTACK, _dmg_move(13), damage=13)
    spew = Move("Spew Coins", IntentType.ATTACK, _multi_hit(2, 8), damage=2)

    def _frail_rider(engine, enemy, target):
        target.add_status(StatusType.FRAIL, 1, applier=enemy)
    throw_relic = Move("Throw Relic", IntentType.ATTACK,
                        _multi_hit(9, 1, _frail_rider), damage=9)

    def _enrage(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    enrage = Move("Enrage", IntentType.BUFF, _enrage, damage=0)
    cycle = [swipe, spew, throw_relic, enrage]
    return Enemy("The Merchant???", 165, cycle, lambda e, t: cycle[t % 4])


def make_battle_friend_v1() -> Enemy:
    return _make_battle_friend(1, 75)


def make_battle_friend_v2() -> Enemy:
    return _make_battle_friend(2, 150)


def make_battle_friend_v3() -> Enemy:
    return _make_battle_friend(3, 300)
