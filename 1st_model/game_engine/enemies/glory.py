"""Act 3, Glory."""

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


def make_devoted_sculptor() -> Enemy:
    """Wiki: HP 162."""
    def _incantation(engine, enemy):
        enemy.add_status(StatusType.RITUAL, 9)
        engine.log.append(f"{enemy.name} gains 9 Ritual")
    incantation = Move("Forbidden Incantation", IntentType.BUFF, _incantation, damage=0)
    savage = Move("Savage", IntentType.ATTACK, _dmg_move(12), damage=12)

    def choose(enemy: Enemy, turn: int) -> Move:
        return incantation if turn == 0 else savage

    return Enemy("Devoted Sculptor", 162, [incantation, savage], choose)


def make_scroll_of_biting() -> Enemy:
    """Wiki: HP 31-38."""
    chomp = Move("Chomp", IntentType.ATTACK, _dmg_move(14), damage=14)

    def _more_teeth(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    more_teeth = Move("More Teeth", IntentType.BUFF, _more_teeth, damage=0)
    chew = Move("Chew", IntentType.ATTACK, _multi_hit(5, 2), damage=5)
    cycle = [chomp, more_teeth, chew]
    return Enemy("Scroll of Biting", CONTENT_RNG.randint(31, 38), cycle,
                  lambda e, t: cycle[t % 3])


def make_axebot() -> Enemy:
    """Wiki: HP 70-78."""
    def _boot_up(engine, enemy):
        enemy.gain_block(10)
        enemy.add_status(StatusType.STRENGTH, 3)
    boot_up = Move("Boot Up", IntentType.DEFEND, _boot_up, damage=0)
    one_two = Move("The One-Two", IntentType.ATTACK, _multi_hit(9, 2), damage=9)

    def _uppercut_rider(engine, enemy, target):
        target.add_status(StatusType.WEAK, 2, applier=enemy)
        target.add_status(StatusType.FRAIL, 2, applier=enemy)
    uppercut = Move("Hammer Uppercut", IntentType.ATTACK,
                     _multi_hit(12, 1, _uppercut_rider), damage=12)
    cycle = [boot_up, one_two, uppercut]
    return Enemy("Axebot", CONTENT_RNG.randint(70, 78), cycle, lambda e, t: cycle[t % 3])


def make_fabricator() -> Enemy:
    """Wiki: HP 150."""
    def _aggressive(enemy):
        return enemy.rng.choice([make_zapbot, make_stabbot])()

    def _defensive(enemy):
        return enemy.rng.choice([make_guardbot, make_noisebot])()

    def _fabricate(engine, enemy):
        engine.summon_enemy([_defensive(enemy), _aggressive(enemy)], summoner=enemy)
    fabricate = Move("Fabricate", IntentType.BUFF, _fabricate, damage=0)

    def _fab_strike(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(18), log=engine.log,
                            label=enemy.name, attacker=enemy)
        engine.summon_enemy(_aggressive(enemy), summoner=enemy)
    fab_strike = Move("Fabricating Strike", IntentType.ATTACK, _fab_strike, damage=18)
    disintegrate = Move("Disintegrate", IntentType.ATTACK, _dmg_move(11), damage=11)
    cycle = [fabricate, disintegrate, fab_strike]
    return Enemy("Fabricator", 150, cycle, lambda e, t: cycle[t % 3])


def make_frog_knight() -> Enemy:
    """Wiki: HP 191."""
    def _frail_rider(engine, enemy, target):
        target.add_status(StatusType.FRAIL, 2, applier=enemy)
    tongue = Move("Tongue Lash", IntentType.ATTACK, _multi_hit(13, 1, _frail_rider), damage=13)
    strike_down = Move("Strike Down Evil", IntentType.ATTACK, _dmg_move(21), damage=21)

    def _for_the_queen(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 5)
    for_queen = Move("For the Queen", IntentType.BUFF, _for_the_queen, damage=0)
    charge = Move("Beetle Charge", IntentType.ATTACK, _dmg_move(35), damage=35)
    cycle = [tongue, for_queen, strike_down, charge]
    return Enemy("Frog Knight", 191, cycle, lambda e, t: cycle[t % 4])


def make_globe_head() -> Enemy:
    """Wiki: HP 148."""
    def _frail_rider(engine, enemy, target):
        target.add_status(StatusType.FRAIL, 2, applier=enemy)
    slap = Move("Shocking Slap", IntentType.ATTACK, _multi_hit(13, 1, _frail_rider), damage=13)
    thunder = Move("Thunder Strike", IntentType.ATTACK, _multi_hit(6, 3), damage=6)

    def _burst_rider(engine, enemy, target):
        enemy.add_status(StatusType.STRENGTH, 2)
    burst = Move("Galvanic Burst", IntentType.ATTACK, _multi_hit(16, 1, _burst_rider), damage=16)
    cycle = [slap, thunder, burst]
    return Enemy("Globe Head", 148, cycle, lambda e, t: cycle[t % 3])


def make_owl_magistrate() -> Enemy:
    """Wiki: HP 234, fixed cycle: Magistrate Scrutiny (16) -> Peck Assault (4 x6) -> Judicial Flight..."""
    scrutiny = Move("Magistrate Scrutiny", IntentType.ATTACK, _dmg_move(16), damage=16)
    peck = Move("Peck Assault", IntentType.ATTACK, _multi_hit(4, 6), damage=4)

    def _flight(engine, enemy):
        enemy.add_status(StatusType.SOAR, 1)
        engine.log.append(f"{enemy.name} takes flight (Soar: 50% less attack damage)")
    flight = Move("Judicial Flight", IntentType.DEFEND, _flight, damage=0)

    def _verdict(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(33), log=engine.log,
                            label=enemy.name, attacker=enemy)
        target.add_status(StatusType.VULNERABLE, 4, applier=enemy)
        enemy.statuses.pop(StatusType.SOAR, None)
    verdict = Move("Verdict", IntentType.ATTACK, _verdict, damage=33)
    cycle = [scrutiny, peck, flight, verdict]
    return Enemy("Owl Magistrate", 234, cycle, lambda e, t: cycle[t % 4])


def make_slimed_berserker() -> Enemy:
    """Wiki: HP 266."""
    def _vomit(engine, enemy):
        _shuffle_status_cards(engine, engine.pick_enemy_attack_target(),
                               make_slimed, 10, "Slimed")
    vomit = Move("Vomit Ichor", IntentType.DEBUFF, _vomit, damage=0)
    pummel = Move("Furious Pummeling", IntentType.ATTACK, _multi_hit(4, 4), damage=4)

    def _hug(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.add_status(StatusType.WEAK, 3, applier=enemy)
        enemy.add_status(StatusType.STRENGTH, 3)
    hug = Move("Leeching Hug", IntentType.DEBUFF, _hug, damage=0)
    smother = Move("Smother", IntentType.ATTACK, _dmg_move(30), damage=30)
    cycle = [vomit, pummel, hug, smother]
    return Enemy("Slimed Berserker", 266, cycle, lambda e, t: cycle[t % 4])


def make_living_shield() -> Enemy:
    """Wiki: HP 55."""
    slam = Move("Shield Slam", IntentType.ATTACK, _dmg_move(6), damage=6)

    def _smash_rider(engine, enemy, target):
        enemy.add_status(StatusType.STRENGTH, 3)
    smash = Move("Smash", IntentType.ATTACK, _multi_hit(16, 1, _smash_rider), damage=16)
    cycle = [slam, smash]
    return Enemy("Living Shield", 55, cycle, lambda e, t: cycle[t % 2])


def make_turret_operator() -> Enemy:
    """Wiki: HP 41. Unload! (3 dmg x5); Loading (gains 1 Strength)."""
    unload = Move("Unload!", IntentType.ATTACK, _multi_hit(3, 5), damage=3)

    def _loading(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 1)
    loading = Move("Loading", IntentType.BUFF, _loading, damage=0)
    cycle = [loading, unload]
    return Enemy("Turret Operator", 41, cycle, lambda e, t: cycle[t % 2])


def make_the_lost() -> Enemy:
    """Wiki: HP 93."""
    def _smog(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.STRENGTH_LOSS, 2, applier=enemy)
        enemy.add_status(StatusType.STRENGTH, 2)
        engine.log.append(f"{enemy.name} drains 2 Strength")
    smog = Move("Debilitating Smog", IntentType.DEBUFF, _smog, damage=0)
    lasers = Move("Eye Lasers", IntentType.ATTACK, _multi_hit(4, 2), damage=4)
    cycle = [smog, lasers]
    return Enemy("The Lost", 93, cycle, lambda e, t: cycle[t % 2])


def make_the_forgotten() -> Enemy:
    """Wiki: HP 106."""
    def _miasma(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.DEXTERITY_LOSS, 2, applier=enemy)
        enemy.gain_block(8)
        enemy.add_status(StatusType.DEXTERITY, 2)
        engine.log.append(f"{enemy.name} drains 2 Dexterity")
    miasma = Move("Miasma", IntentType.DEBUFF, _miasma, damage=0)

    def _dread(engine, enemy):
        bonus = enemy.get_status(StatusType.DEXTERITY)
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(13 + bonus), log=engine.log,
                            label=enemy.name, attacker=enemy)
    dread = Move("Dread", IntentType.ATTACK, _dread, damage=13)
    cycle = [miasma, dread]
    return Enemy("The Forgotten", 106, cycle, lambda e, t: cycle[t % 2])


def make_mecha_knight() -> Enemy:
    """Wiki: Elite, HP 300."""
    charge = Move("Charge", IntentType.ATTACK, _dmg_move(25), damage=25)

    def _flamethrower(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(4):
            target.add_to_hand(make_burn(), engine.log)
        engine.log.append(f"{target.name} gains 4 Burn in hand ({enemy.name})")
    flamethrower = Move("Flamethrower", IntentType.DEBUFF, _flamethrower, damage=0)

    def _windup(engine, enemy):
        enemy.gain_block(15)
        enemy.add_status(StatusType.STRENGTH, 5)
    windup = Move("Windup", IntentType.DEFEND, _windup, damage=0)
    cleave = Move("Heavy Cleave", IntentType.ATTACK, _dmg_move(35), damage=35)
    cycle = [charge, flamethrower, windup, cleave]
    return Enemy("Mecha Knight", 300, cycle, lambda e, t: cycle[t % 4], category="elite")


def make_soul_nexus() -> Enemy:
    """Wiki: Elite, HP 234."""
    soul_burn = Move("Soul Burn", IntentType.ATTACK, _dmg_move(29), damage=29)
    maelstrom = Move("Maelstrom", IntentType.ATTACK, _multi_hit(6, 4), damage=6)

    def _drain_rider(engine, enemy, target):
        target.add_status(StatusType.VULNERABLE, 2, applier=enemy)
    drain = Move("Drain Life", IntentType.ATTACK, _multi_hit(18, 1, _drain_rider), damage=18)
    cycle = [maelstrom, drain, soul_burn]
    return Enemy("Soul Nexus", 234, cycle, lambda e, t: cycle[t % 3], category="elite")


def make_knight_gang() -> List[Enemy]:
    """Wiki: Elite, THREE knights, each with a standing rule that lasts only while it lives:"""
    def _breaker(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 3)
    breaker = Move("Breaker", IntentType.BUFF, _breaker, damage=0)
    flail = Move("Flail", IntentType.ATTACK, _multi_hit(9, 2), damage=9)
    ram15 = Move("Ram", IntentType.ATTACK, _dmg_move(15), damage=15)
    flail_cycle = [ram15, flail, breaker, flail]
    flail_knight = Enemy("Flail Knight", 101, flail_cycle,
                          lambda e, t: flail_cycle[t % len(flail_cycle)], category="elite")

    def _hex(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.HEX, 2, applier=enemy)
        engine.log.append(f"{enemy.name} applies 2 Hex (your cards are Ethereal)")
    hex_move = Move("Hex", IntentType.DEBUFF, _hex, damage=0)
    soul_slash = Move("Soul Slash", IntentType.ATTACK, _dmg_move(15), damage=15)
    soul_flame = Move("Soul Flame", IntentType.ATTACK, _multi_hit(3, 3), damage=3)
    spectral_cycle = [hex_move, soul_slash, soul_flame]

    def _spectral_death(engine, enemy):
        for p in engine.players:
            p.statuses.pop(StatusType.HEX, None)
        engine.log.append("Hex fades with the Spectral Knight")
    spectral = Enemy("Spectral Knight", 93, spectral_cycle,
                      lambda e, t: spectral_cycle[t % len(spectral_cycle)], category="elite")
    spectral.on_death = _spectral_death

    def _power_shield_rider(engine, enemy, target):
        enemy.gain_block(5)
    power_shield = Move("Power Shield", IntentType.ATTACK,
                         _multi_hit(6, 1, _power_shield_rider), damage=6)

    def _dampen(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.DOWNGRADED, 1, applier=enemy)
        engine.log.append(f"{enemy.name} applies Downgraded (cards lose their upgrades)")
    dampen = Move("Dampen", IntentType.DEBUFF, _dampen, damage=0)
    ram10 = Move("Ram", IntentType.ATTACK, _dmg_move(10), damage=10)

    def _prep(engine, enemy):
        enemy.gain_block(5)
    prep = Move("Prep", IntentType.DEFEND, _prep, damage=0)
    magic_bomb = Move("Magic Bomb", IntentType.ATTACK, _dmg_move(35), damage=35)
    magi_tail = [ram10, prep, magic_bomb]

    def magi_choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return power_shield
        if turn == 1:
            return dampen
        return magi_tail[(turn - 2) % len(magi_tail)]

    def _magi_death(engine, enemy):
        for p in engine.players:
            p.statuses.pop(StatusType.DOWNGRADED, None)
        engine.log.append("Downgraded fades with the Magi Knight")
    magi = Enemy("Magi Knight", 82, [power_shield, dampen] + magi_tail,
                  magi_choose, category="elite")
    magi.on_death = _magi_death
    return [flail_knight, spectral, magi]


def make_queen() -> List[Enemy]:
    """Wiki: Boss, HP 400, fighting alongside ONE Torch Head Amalgam (199)."""
    amalgam_moves = [
        Move("Strong Tackle", IntentType.ATTACK, _dmg_move(26), damage=26),
        Move("Tackle", IntentType.ATTACK, _dmg_move(18), damage=18),
        Move("Beam", IntentType.ATTACK, _multi_hit(8, 3), damage=8),
        Move("Weak Tackle", IntentType.ATTACK, _dmg_move(14), damage=14),
    ]
    amalgam = Enemy("Torch Head Amalgam", 199, amalgam_moves,
                     lambda e, t: amalgam_moves[t % len(amalgam_moves)], category="boss")

    def _puppet_strings(engine, enemy):
        for p in engine.players_alive():
            p.chains_of_binding = 3
        engine.log.append(f"{enemy.name} applies 3 Chains of Binding")
    puppet = Move("Puppet Strings", IntentType.DEBUFF, _puppet_strings, damage=0)

    def _youre_mine(engine, enemy):
        for p in engine.players_alive():
            for s in (StatusType.FRAIL, StatusType.WEAK, StatusType.VULNERABLE):
                p.add_status(s, 99, applier=enemy)
        engine.log.append(f"{enemy.name}: 99 Frail, Weak and Vulnerable to all players")
    youre_mine = Move("You're Mine", IntentType.DEBUFF, _youre_mine, damage=0)

    def _burn_bright(engine, enemy):
        if amalgam.alive:
            amalgam.add_status(StatusType.STRENGTH, 1)
        enemy.gain_block(20)
    burn_bright = Move("Burn Bright for Me", IntentType.DEFEND, _burn_bright, damage=0)
    off_with = Move("Off with Your Head", IntentType.ATTACK, _multi_hit(3, 5), damage=3)
    execution = Move("Execution", IntentType.ATTACK, _dmg_move(15), damage=15)

    def _enrage(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    enrage = Move("Enrage", IntentType.BUFF, _enrage, damage=0)
    enraged_cycle = [off_with, execution, enrage]

    def queen_choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return puppet
        if turn == 1:
            return youre_mine
        if amalgam.alive:
            return burn_bright
        i = getattr(enemy, "enraged_turn", None)
        if i is None:
            enemy.enraged_turn = 0
            return enrage
        enemy.enraged_turn = i + 1
        return enraged_cycle[i % len(enraged_cycle)]

    queen = Enemy("Queen", 400, [puppet, youre_mine, burn_bright] + enraged_cycle,
                   queen_choose, category="boss")
    amalgam.leader = None
    return [queen, amalgam]


def make_test_subject() -> Enemy:
    """Wiki: Boss, three phases with SEPARATE HP pools: 100 -> 200 -> 300."""
    bite = Move("Bite", IntentType.ATTACK, _dmg_move(20), damage=20)

    def _skull_rider(engine, enemy, target):
        target.add_status(StatusType.VULNERABLE, 1, applier=enemy)
    skull_bash = Move("Skull Bash", IntentType.ATTACK, _multi_hit(14, 1, _skull_rider), damage=14)
    p1 = [bite, skull_bash]

    def _multi_claw(engine, enemy):
        hits = 3 + getattr(enemy, "claw_uses", 0)
        enemy.claw_uses = getattr(enemy, "claw_uses", 0) + 1
        target = engine.pick_enemy_attack_target()
        for _ in range(hits):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(10), log=engine.log,
                                label=enemy.name, attacker=enemy)
    multi_claw = Move("Multi-Claw", IntentType.ATTACK, _multi_claw, damage=10)

    lacerate = Move("Lacerate", IntentType.ATTACK, _multi_hit(10, 3), damage=10)
    big_pounce = Move("Big Pounce", IntentType.ATTACK, _dmg_move(45), damage=45)

    def _growl(engine, enemy):
        _shuffle_status_cards(engine, engine.pick_enemy_attack_target(),
                               make_burn, 3, "Burn")
        enemy.add_status(StatusType.STRENGTH, 2)
    growl = Move("Burning Growl", IntentType.DEBUFF, _growl, damage=0)
    p3 = [lacerate, big_pounce, growl]

    def choose(enemy: Enemy, turn: int) -> Move:
        phase = getattr(enemy, "phase", 1)
        if phase == 1:
            return p1[turn % len(p1)]
        if phase == 2:
            return multi_claw
        i = getattr(enemy, "p3_turn", 0)
        enemy.p3_turn = i + 1
        if i % 2 == 1:
            enemy.add_status(StatusType.INTANGIBLE, 1)
        return p3[i % len(p3)]

    def _adaptable(engine, enemy):
        phase = getattr(enemy, "phase", 1)
        if phase >= 3:
            return
        enemy.phase = phase + 1
        enemy.max_hp = 200 if enemy.phase == 2 else 300
        enemy.hp = enemy.max_hp
        enemy.alive = True
        enemy.death_resolved = False
        enemy.turn_count = 0
        if enemy.phase == 2:
            enemy.painful_stabs = 1
        else:
            enemy.painful_stabs = 0
        engine.log.append(
            f"{enemy.name} adapts: phase {enemy.phase} with {enemy.max_hp} HP")

    e = Enemy("Test Subject", 100, p1 + [multi_claw] + p3, choose, category="boss")
    e.phase = 1
    e.on_death = _adaptable
    return e


def make_aeonglass() -> Enemy:
    """Wiki: Boss, HP 512."""
    def _ebb(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(22), log=engine.log,
                            label=enemy.name, attacker=enemy)
        enemy.gain_block(33)
    ebb = Move("Ebb", IntentType.ATTACK, _ebb, damage=22)
    lasers = Move("Eye Lasers", IntentType.ATTACK, _multi_hit(11, 2), damage=11)

    def _intensity(engine, enemy):
        x = getattr(enemy, "intensity_uses", 0)
        enemy.intensity_uses = x + 1
        target = engine.pick_enemy_attack_target()
        target.discard_pile.append(make_wither(x))
        enemy.add_status(StatusType.STRENGTH, 2 + x)
        engine.log.append(
            f"{enemy.name} intensifies: Wither+{x} added, gains {2 + x} Strength")
    intensity = Move("Increasing Intensity", IntentType.DEBUFF, _intensity, damage=0)
    cycle = [ebb, lasers, intensity]
    return Enemy("Aeonglass", 512, cycle, lambda e, t: cycle[t % 3], category="boss")


def make_doormaker() -> Enemy:
    """Wiki: HP 489, listed under Glory bosses."""
    def _open(engine, enemy):
        engine.log.append(f"{enemy.name} opens dramatically (next: Hunger)")
    dramatic = Move("Dramatic Open", IntentType.BUFF, _open, damage=0)
    hunger = Move("Hunger", IntentType.ATTACK, _dmg_move(30), damage=30)
    scrutiny = Move("Scrutiny", IntentType.ATTACK, _dmg_move(24), damage=24)

    def _grasp_rider(engine, enemy, target):
        enemy.add_status(StatusType.STRENGTH, 3)
    grasp = Move("Grasp", IntentType.ATTACK, _multi_hit(10, 2, _grasp_rider), damage=10)
    rotation = [hunger, scrutiny, grasp]

    def choose(enemy: Enemy, turn: int) -> Move:
        return dramatic if turn == 0 else rotation[(turn - 1) % len(rotation)]

    return Enemy("Doormaker", 489, [dramatic] + rotation, choose, category="boss")
