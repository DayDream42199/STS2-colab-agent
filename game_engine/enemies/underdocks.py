"""Act 1, Underdocks."""

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


def make_calcified_cultist() -> Enemy:
    """Wiki: HP 38-41. Incantation (gain 2 Ritual); Dark Strike (9 dmg)."""
    return _make_cultist("Calcified Cultist", (38, 41), 2, 9)


def make_damp_cultist() -> Enemy:
    """Wiki: HP 51-53."""
    return _make_cultist("Damp Cultist", (51, 53), 5, 1)


def make_seapunk() -> Enemy:
    """Wiki: HP 44-46."""
    sea_kick = Move("Sea Kick", IntentType.ATTACK, _dmg_move(11), damage=11)

    def _spinning_kick(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(4):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(2), log=engine.log, label=enemy.name, attacker=enemy)
    spinning_kick = Move("Spinning Kick", IntentType.ATTACK, _spinning_kick, damage=2)

    def _bubble_burp(engine, enemy):
        enemy.gain_block(7)
        enemy.add_status(StatusType.STRENGTH, 1)
    bubble_burp = Move("Bubble Burp", IntentType.DEFEND, _bubble_burp, damage=0)

    cycle = [sea_kick, spinning_kick, bubble_burp]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    return Enemy("Seapunk", CONTENT_RNG.randint(44, 46),
                  [sea_kick, spinning_kick, bubble_burp], choose)


def make_sludge_spinner() -> Enemy:
    """Wiki: HP 37-39."""
    def _oil_spray(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(8), log=engine.log, label=enemy.name, attacker=enemy)
        target.add_status(StatusType.WEAK, 1)
    oil_spray = Move("Oil Spray", IntentType.ATTACK_DEBUFF, _oil_spray, damage=8)
    slam = Move("Slam", IntentType.ATTACK, _dmg_move(11), damage=11)

    def _rage(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(6), log=engine.log, label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.STRENGTH, 3)
    rage = Move("Rage", IntentType.ATTACK, _rage, damage=6)

    cycle = [oil_spray, slam, rage]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    return Enemy("Sludge Spinner", CONTENT_RNG.randint(37, 39), [oil_spray, slam, rage], choose)


def make_sewer_clam() -> Enemy:
    """Wiki: HP 56, starts with Plating 8."""
    jet = Move("Jet", IntentType.ATTACK, _dmg_move(10), damage=10)

    def _pressurize(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 4)
    pressurize = Move("Pressurize", IntentType.BUFF, _pressurize, damage=0)

    cycle = [jet, pressurize]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    clam = Enemy("Sewer Clam", 56, [jet, pressurize], choose)
    clam.add_status(StatusType.PLATED_ARMOR, 8)
    return clam


def make_punch_construct() -> Enemy:
    """Wiki: HP 55, starts with Artifact 1."""
    def _ready(engine, enemy):
        enemy.gain_block(10)
    ready = Move("READY", IntentType.DEFEND, _ready, damage=0)

    def _fast_punch(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(2):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(5), log=engine.log, label=enemy.name, attacker=enemy)
        target.add_status(StatusType.FRAIL, 1)
    fast_punch = Move("Fast Punch", IntentType.ATTACK_DEBUFF, _fast_punch, damage=5)
    strong_punch = Move("Strong Punch", IntentType.ATTACK, _dmg_move(14), damage=14)

    punches = [fast_punch, strong_punch]

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return ready
        return punches[(turn - 1) % len(punches)]

    construct = Enemy("Punch Construct", 55, [ready, fast_punch, strong_punch], choose)
    construct.add_status(StatusType.ARTIFACT, 1)
    return construct


def make_haunted_ship() -> Enemy:
    """Wiki: HP 63."""
    def _haunt(engine, enemy):
        target = engine.pick_enemy_attack_target()
        _shuffle_status_cards(engine, target, make_dazed, 5, "Dazed")
        target.add_status(StatusType.WEAK, 3)
    haunt = Move("Haunt", IntentType.DEBUFF, _haunt, damage=0)
    swipe = Move("Swipe", IntentType.ATTACK, _dmg_move(13), damage=13)

    def _stomp(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(3):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(4), log=engine.log, label=enemy.name, attacker=enemy)
    stomp = Move("Stomp", IntentType.ATTACK, _stomp, damage=4)

    attacks = [swipe, stomp]

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return haunt
        return attacks[(turn - 1) % len(attacks)]

    return Enemy("Haunted Ship", 63, [haunt, swipe, stomp], choose)


def make_toadpole(start_offset: int = 0) -> Enemy:
    """Wiki: HP 21-25."""
    whirl = Move("Whirl", IntentType.ATTACK, _dmg_move(7), damage=7)

    def _spiken(engine, enemy):
        enemy.add_status(StatusType.THORNS, 2)
        engine.log.append(f"{enemy.name} gains 2 Thorns")
    spiken = Move("Spiken", IntentType.BUFF, _spiken, damage=0)

    def _spike_spit(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(3):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(3), log=engine.log,
                                label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.THORNS, -2)
        engine.log.append(f"{enemy.name} loses 2 Thorns (Spike Spit)")
    spike_spit = Move("Spike Spit", IntentType.ATTACK, _spike_spit, damage=3)

    cycle = [whirl, spiken, spike_spit]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[(turn + start_offset) % len(cycle)]

    return Enemy("Toadpole", CONTENT_RNG.randint(21, 25), list(cycle), choose)


def make_toadpole_pair() -> List[Enemy]:
    """Wiki encounter "Toadpoles (Weak)": Toadpole x2, with the FRONT one starting on Spiken instead of..."""
    return [make_toadpole(start_offset=1), make_toadpole(start_offset=0)]


def make_phantasmal_gardener_group() -> List[Enemy]:
    """Wiki: HP 26-31 each, Skittish 6 each, and they fight as FOUR."""
    bite = Move("Bite", IntentType.ATTACK, _dmg_move(5), damage=5)
    lash = Move("Lash", IntentType.ATTACK, _dmg_move(7), damage=7)

    def _flail(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(3):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(1), log=engine.log, label=enemy.name, attacker=enemy)
    flail = Move("Flail", IntentType.ATTACK, _flail, damage=1)

    def _enlarge(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    enlarge = Move("Enlarge", IntentType.BUFF, _enlarge, damage=0)

    cycle = [bite, lash, flail, enlarge]

    def _make_choose(offset):
        def choose(enemy: Enemy, turn: int) -> Move:
            return cycle[(turn + offset) % len(cycle)]
        return choose

    gardeners = []
    for offset in range(4):
        g = Enemy("Phantasmal Gardener", CONTENT_RNG.randint(26, 31),
                   list(cycle), _make_choose(offset), category="elite")
        g.add_status(StatusType.SKITTISH, 6)
        gardeners.append(g)
    return gardeners


def make_corpse_slug() -> Enemy:
    """Wiki: HP 25-27. Whip Slap (3 dmg x2); Glomp (8 dmg); Goop (2 Frail)."""
    whip_slap = Move("Whip Slap", IntentType.ATTACK, _multi_hit(3, 2), damage=3)
    glomp = Move("Glomp", IntentType.ATTACK, _dmg_move(8), damage=8)

    def _goop(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.add_status(StatusType.FRAIL, 2, applier=enemy)
        engine.log.append(f"{target.name} gains 2 Frail ({enemy.name})")
    goop = Move("Goop", IntentType.DEBUFF, _goop, damage=0)
    cycle = [whip_slap, glomp, goop]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    e = Enemy("Corpse Slug", CONTENT_RNG.randint(25, 27), cycle, choose)
    e.add_status(StatusType.RAVENOUS, 2)
    return e


def make_fossil_stalker() -> Enemy:
    """Wiki: HP 51-53."""
    latch = Move("Latch", IntentType.ATTACK, _dmg_move(12), damage=12)

    def _frail_rider(engine, enemy, target):
        target.add_status(StatusType.FRAIL, 1, applier=enemy)
    tackle = Move("Tackle", IntentType.ATTACK, _multi_hit(9, 1, _frail_rider), damage=9)
    lash = Move("Lash", IntentType.ATTACK, _multi_hit(3, 2), damage=3)
    cycle = [latch, tackle, lash]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    e = Enemy("Fossil Stalker", CONTENT_RNG.randint(51, 53), cycle, choose)
    e.add_status(StatusType.SUCK, 2)
    return e


def make_gremlin_merc() -> Enemy:
    """Wiki: HP 47-49."""
    gimme = Move("Gimme", IntentType.ATTACK, _multi_hit(7, 2), damage=7)

    def _weak_rider(engine, enemy, target):
        target.add_status(StatusType.WEAK, 2, applier=enemy)
    double_smash = Move("Double Smash", IntentType.ATTACK,
                         _multi_hit(6, 2, _weak_rider), damage=6)

    def _str_rider(engine, enemy, target):
        enemy.add_status(StatusType.STRENGTH, 2)
    hehe = Move("Hehe", IntentType.ATTACK, _multi_hit(8, 1, _str_rider), damage=8)
    cycle = [gimme, double_smash, hehe]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    def _on_death(engine, enemy):
        engine.summon_enemy([make_fat_gremlin(), make_sneaky_gremlin()],
                             summoner=enemy, stunned=True)

    e = Enemy("Gremlin Merc", CONTENT_RNG.randint(47, 49), cycle, choose)
    e.on_death = _on_death
    return e


def make_living_fog() -> Enemy:
    """Wiki: HP 80."""
    def _advanced_gas(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(8), log=engine.log,
                            label=enemy.name, attacker=enemy)
        target.add_status(StatusType.SMOGGY, 1, applier=enemy)
        engine.log.append(f"{target.name} gains 1 Smoggy (1 Skill per turn)")
    advanced_gas = Move("Advanced Gas", IntentType.DEBUFF, _advanced_gas, damage=8)

    def _bloat(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(5), log=engine.log,
                            label=enemy.name, attacker=enemy)
        engine.summon_enemy(make_gas_bomb(), summoner=enemy)
    bloat = Move("Bloat", IntentType.ATTACK, _bloat, damage=5)
    super_gas = Move("Super Gas Blast", IntentType.ATTACK, _dmg_move(8), damage=8)

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return advanced_gas
        return bloat if turn % 2 == 1 else super_gas

    return Enemy("Living Fog", 80, [advanced_gas, bloat, super_gas], choose)


def make_two_tailed_rat() -> Enemy:
    """Wiki: HP 17-21."""
    scratch = Move("Scratch", IntentType.ATTACK, _dmg_move(8), damage=8)
    disease_bite = Move("Disease Bite", IntentType.ATTACK, _dmg_move(6), damage=6)

    def _screech(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.add_status(StatusType.FRAIL, 1, applier=enemy)
    screech = Move("Screech", IntentType.DEBUFF, _screech, damage=0)

    def _call_for_backup(engine, enemy):
        engine.summon_enemy(make_two_tailed_rat(), summoner=enemy, stunned=True)
    backup = Move("Call for Backup", IntentType.BUFF, _call_for_backup, damage=0)
    cycle = [scratch, backup, disease_bite, screech]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    return Enemy("Two-Tailed Rat", CONTENT_RNG.randint(17, 21),
                  [scratch, disease_bite, screech, backup], choose)


def make_skulking_colony() -> Enemy:
    """Wiki: Elite, HP 75."""
    zoom = Move("Zoom", IntentType.ATTACK, _dmg_move(14), damage=14)

    def _str_rider(engine, enemy, target):
        enemy.add_status(StatusType.STRENGTH, 2)
    inertia = Move("Inertia", IntentType.ATTACK, _multi_hit(9, 1, _str_rider), damage=9)
    stabs = Move("Piercing Stabs", IntentType.ATTACK, _multi_hit(7, 2), damage=7)
    cycle = [zoom, inertia, stabs]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    return Enemy("Skulking Colony", 75, cycle, choose, category="elite")


def make_terror_eel() -> Enemy:
    """Wiki: Elite, HP 140."""
    crash = Move("Crash", IntentType.ATTACK, _dmg_move(16), damage=16)

    def _vigor_rider(engine, enemy, target):
        enemy.add_status(StatusType.VIGOR, 6)
        engine.log.append(f"{enemy.name} gains 6 Vigor")
    thrash = Move("Thrash", IntentType.ATTACK, _multi_hit(3, 3, _vigor_rider), damage=3)
    stun = Move("Stun", IntentType.BUFF, _nothing, damage=0)

    def _terror(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.VULNERABLE, 99, applier=enemy)
        engine.log.append(f"{enemy.name} applies 99 Vulnerable")
    terror = Move("Terror", IntentType.DEBUFF, _terror, damage=0)
    cycle = [terror, crash, thrash, stun]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    return Enemy("Terror Eel", 140, cycle, choose, category="elite")


def make_lagavulin_matriarch() -> Enemy:
    """Wiki: Boss, HP 222."""
    sleep = Move("Sleep", IntentType.BUFF, _nothing, damage=0)
    slash = Move("Slash", IntentType.ATTACK, _dmg_move(19), damage=19)
    disembowel = Move("Disembowel", IntentType.ATTACK, _multi_hit(9, 2), damage=9)

    def _block_rider(engine, enemy, target):
        enemy.gain_block(12)
    slash2 = Move("Guarded Slash", IntentType.ATTACK, _multi_hit(12, 1, _block_rider), damage=12)

    def _soul_siphon(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.STRENGTH_LOSS, 2, applier=enemy)
            p.add_status(StatusType.DEXTERITY_LOSS, 2, applier=enemy)
        enemy.add_status(StatusType.STRENGTH, 2)
        engine.log.append(f"{enemy.name} siphons 2 Strength and 2 Dexterity")
    soul_siphon = Move("Soul Siphon", IntentType.DEBUFF, _soul_siphon, damage=0)
    cycle = [slash, disembowel, slash2, soul_siphon]

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return sleep
        return cycle[(turn - 1) % len(cycle)]

    return Enemy("Lagavulin Matriarch", 222,
                  [sleep] + cycle, choose, category="boss")


def make_soul_fysh() -> Enemy:
    """Wiki: Boss, HP 211."""
    def _beckon(engine, enemy):
        target = engine.pick_enemy_attack_target()
        card = make_beckon()
        target.draw_pile.insert(0, card)
        target.discard_pile.append(make_beckon())
        engine.log.append(f"{target.name} gets 2 Beckon (1 draw pile, 1 discard)")
    beckon = Move("Beckon", IntentType.DEBUFF, _beckon, damage=0)
    de_gas = Move("De-Gas", IntentType.ATTACK, _dmg_move(16), damage=16)

    def _gaze_rider(engine, enemy, target):
        _shuffle_status_cards(engine, target, make_beckon, 1, "Beckon")
    gaze = Move("Gaze", IntentType.ATTACK, _multi_hit(7, 1, _gaze_rider), damage=7)

    def _fade(engine, enemy):
        enemy.add_status(StatusType.INTANGIBLE, 2)
        engine.log.append(f"{enemy.name} gains 2 Intangible")
    fade = Move("Fade", IntentType.BUFF, _fade, damage=0)

    def _scream_rider(engine, enemy, target):
        target.add_status(StatusType.VULNERABLE, 3, applier=enemy)
    scream = Move("Scream", IntentType.ATTACK, _multi_hit(13, 1, _scream_rider), damage=13)
    cycle = [beckon, de_gas, gaze, fade, scream]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    return Enemy("Soul Fysh", 211, cycle, choose, category="boss")


def make_waterfall_giant() -> Enemy:
    """Wiki: Boss, HP 240."""
    def _steam(enemy, amount=3):
        enemy.add_status(StatusType.STEAM_ERUPTION, amount)

    def _pressurize(engine, enemy):
        _steam(enemy, 15)
        engine.log.append(f"{enemy.name} gains 15 Steam Eruption")
    pressurize = Move("Pressurize", IntentType.BUFF, _pressurize, damage=0)

    def _stomp(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(15), log=engine.log,
                            label=enemy.name, attacker=enemy)
        target.add_status(StatusType.WEAK, 1, applier=enemy)
        _steam(enemy)
    stomp = Move("Stomp", IntentType.ATTACK, _stomp, damage=15)

    def _ram(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(10), log=engine.log,
                            label=enemy.name, attacker=enemy)
        _steam(enemy)
    ram = Move("Ram", IntentType.ATTACK, _ram, damage=10)

    def _siphon(engine, enemy):
        healed = 15 * len(engine.players)
        enemy.heal(healed)
        _steam(enemy)
        engine.log.append(f"{enemy.name} heals {healed} HP (15 per player)")
    siphon = Move("Siphon", IntentType.BUFF, _siphon, damage=0)

    def _pressure_gun(engine, enemy):
        dmg = 20 + 5 * getattr(enemy, "pressure_gun_uses", 0)
        enemy.pressure_gun_uses = getattr(enemy, "pressure_gun_uses", 0) + 1
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(dmg), log=engine.log,
                            label=enemy.name, attacker=enemy)
        _steam(enemy)
    pressure_gun = Move("Pressure Gun", IntentType.ATTACK, _pressure_gun, damage=20)

    def _pressure_up(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(13), log=engine.log,
                            label=enemy.name, attacker=enemy)
        _steam(enemy)
    pressure_up = Move("Pressure Up", IntentType.ATTACK, _pressure_up, damage=13)

    cycle = [pressurize, stomp, ram, pressure_gun, siphon, pressure_up]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    return Enemy("Waterfall Giant", 240, cycle, choose, category="boss")
