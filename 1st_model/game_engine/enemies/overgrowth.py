"""Act 1, Overgrowth."""

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


def make_nibbit() -> Enemy:
    """Wiki: HP 42-46."""
    butt = Move("Butt", IntentType.ATTACK, _dmg_move(12), damage=12)

    def _hesitant_slice(engine, enemy):
        dmg = enemy.deal_attack_damage(6)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        enemy.gain_block(5)
    hesitant_slice = Move("Hesitant Slice", IntentType.ATTACK, _hesitant_slice, damage=6)

    def _hiss(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    hiss = Move("Hiss", IntentType.BUFF, _hiss, damage=0)

    cycle = [hesitant_slice, hiss, butt]

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return butt
        return cycle[(turn - 1) % len(cycle)]

    hp = CONTENT_RNG.randint(42, 46)
    return Enemy("Nibbit", hp, [butt, hesitant_slice, hiss], choose)


def make_shrinker_beetle() -> Enemy:
    """Wiki: HP 38-40."""
    def _shrinker(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.add_status(StatusType.SHRINK, 3, applier=enemy)
        engine.log.append(f"{target.name} is Shrunk for 3 turns ({enemy.name})")
    shrinker = Move("Shrinker", IntentType.DEBUFF, _shrinker, damage=0)
    chomp = Move("Chomp", IntentType.ATTACK, _dmg_move(7), damage=7)
    stomp = Move("Stomp", IntentType.ATTACK, _dmg_move(13), damage=13)

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return shrinker
        return chomp if turn % 2 == 1 else stomp

    hp = CONTENT_RNG.randint(38, 40)
    return Enemy("Shrinker Beetle", hp, [shrinker, chomp, stomp], choose)


def make_fuzzy_wurm_crawler() -> Enemy:
    """Wiki: HP 55-57. 3-turn repeating cycle: Acid Goop (attack 4), Inhale (buff: gain 7 Strength)..."""
    acid_goop = Move("Acid Goop", IntentType.ATTACK, _dmg_move(4), damage=4)

    def _inhale(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 7)
    inhale = Move("Inhale", IntentType.BUFF, _inhale, damage=0)

    cycle = [acid_goop, inhale, acid_goop]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    hp = CONTENT_RNG.randint(55, 57)
    return Enemy("Fuzzy Wurm Crawler", hp, [acid_goop, inhale], choose)


def make_inklet_trio() -> List[Enemy]:
    """Wiki: HP 11-17 each."""
    jab = Move("Jab", IntentType.ATTACK, _dmg_move(3), damage=3)

    def _windup_punch(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(3):
            if not target.alive:
                break
            dmg = enemy.deal_attack_damage(2)
            target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
    windup_punch = Move("Windup Punch", IntentType.ATTACK, _windup_punch, damage=2)
    piercing_gaze = Move("Piercing Gaze", IntentType.ATTACK, _dmg_move(10), damage=10)
    moveset = [jab, windup_punch, piercing_gaze]

    def _make_choose(position):
        def choose(enemy: Enemy, turn: int) -> Move:
            if turn == 0:
                if position == "middle":
                    return windup_punch
                return jab if enemy.rng.random() < 0.7 else windup_punch
            if enemy.current_move is jab:
                return enemy.rng.choice([piercing_gaze, windup_punch])
            return jab
        return choose

    inklets = []
    for position in ("outer", "middle", "outer"):
        hp = CONTENT_RNG.randint(11, 17)
        e = Enemy("Inklet", hp, list(moveset), _make_choose(position))
        e.add_status(StatusType.SLIPPERY, 1)
        inklets.append(e)
    return inklets


def make_byrdonis() -> Enemy:
    """Wiki: HP 81-84."""
    def _swoop(engine, enemy):
        dmg = enemy.deal_attack_damage(17)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.STRENGTH, 1)
    swoop = Move("Swoop", IntentType.ATTACK, _swoop, damage=17)

    def _peck(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(3):
            if not target.alive:
                break
            dmg = enemy.deal_attack_damage(3)
            target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.STRENGTH, 1)
    peck = Move("Peck", IntentType.ATTACK, _peck, damage=3)

    cycle = [swoop, peck]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    hp = CONTENT_RNG.randint(81, 84)
    return Enemy("Byrdonis", hp, [swoop, peck], choose, category="elite")


def make_vantom() -> Enemy:
    """Wiki: HP 173 (a single confirmed value, not a range)."""
    ink_blot = Move("Ink Blot", IntentType.ATTACK, _dmg_move(7), damage=7)

    def _inky_lance(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(2):
            if not target.alive:
                break
            dmg = enemy.deal_attack_damage(6)
            target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
    inky_lance = Move("Inky Lance", IntentType.ATTACK, _inky_lance, damage=6)

    def _dismember(engine, enemy):
        target = engine.pick_enemy_attack_target()
        dmg = enemy.deal_attack_damage(27)
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        if target.alive:
            for _ in range(3):
                target.discard_pile.append(make_wound())
            engine.log.append(f"{target.name} has 3 Wounds shuffled into their discard pile ({enemy.name})")
    dismember = Move("Dismember", IntentType.ATTACK_DEBUFF, _dismember, damage=27)

    def _prepare(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    prepare = Move("Prepare", IntentType.BUFF, _prepare, damage=0)

    cycle = [ink_blot, inky_lance, dismember, prepare]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    vantom = Enemy("Vantom", 173, [ink_blot, inky_lance, dismember, prepare], choose,
                    category="boss")
    vantom.add_status(StatusType.SLIPPERY, 9)
    return vantom


def make_assassin_raider() -> Enemy:
    """Wiki: HP 18-23. Single move: Killshot (10 dmg)."""
    killshot = Move("Killshot", IntentType.ATTACK, _dmg_move(10), damage=10)

    def choose(enemy: Enemy, turn: int) -> Move:
        return killshot

    hp = CONTENT_RNG.randint(18, 23)
    return Enemy("Assassin Raider", hp, [killshot], choose)


def make_axe_raider() -> Enemy:
    """Wiki: HP 20-22."""
    def _swing(engine, enemy):
        dmg = enemy.deal_attack_damage(5)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        enemy.gain_block(5)
    swing = Move("Swing", IntentType.ATTACK, _swing, damage=5)
    big_swing = Move("Big Swing", IntentType.ATTACK, _dmg_move(12), damage=12)
    cycle = [swing, big_swing]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    hp = CONTENT_RNG.randint(20, 22)
    return Enemy("Axe Raider", hp, [swing, big_swing], choose)


def make_brute_raider() -> Enemy:
    """Wiki: HP 30-33."""
    beat = Move("Beat", IntentType.ATTACK, _dmg_move(7), damage=7)

    def _clap(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 3)
    clap = Move("Clap", IntentType.BUFF, _clap, damage=0)
    cycle = [beat, clap]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    hp = CONTENT_RNG.randint(30, 33)
    return Enemy("Brute Raider", hp, [beat, clap], choose)


def make_crossbow_raider() -> Enemy:
    """Wiki: HP 18-21."""
    def _reload(engine, enemy):
        enemy.gain_block(3)
    reload_ = Move("Reload", IntentType.DEFEND, _reload, damage=0)
    fire = Move("Fire!", IntentType.ATTACK, _dmg_move(14), damage=14)
    cycle = [reload_, fire]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    hp = CONTENT_RNG.randint(18, 21)
    return Enemy("Crossbow Raider", hp, [reload_, fire], choose)


def make_tracker_raider() -> Enemy:
    """Wiki: HP 21-25."""
    def _track(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.add_status(StatusType.FRAIL, 2)
        engine.log.append(f"{target.name} gains 2 Frail ({enemy.name})")
    track = Move("Track", IntentType.DEBUFF, _track, damage=0)

    def _unleash(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(8):
            if not target.alive:
                break
            dmg = enemy.deal_attack_damage(1)
            target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
    unleash = Move("Unleash the Hounds", IntentType.ATTACK, _unleash, damage=1)
    cycle = [track, unleash]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    hp = CONTENT_RNG.randint(21, 25)
    return Enemy("Tracker Raider", hp, [track, unleash], choose)


def make_cubex_construct() -> Enemy:
    """Wiki: HP 65."""
    def _charge_up(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    charge_up = Move("Charge Up", IntentType.BUFF, _charge_up, damage=0)

    def _repeater_blast(engine, enemy):
        dmg = enemy.deal_attack_damage(7)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.STRENGTH, 2)
    repeater_blast = Move("Repeater Blast", IntentType.ATTACK, _repeater_blast, damage=7)

    def _expel_blast(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(2):
            if not target.alive:
                break
            dmg = enemy.deal_attack_damage(5)
            target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
    expel_blast = Move("Expel Blast", IntentType.ATTACK, _expel_blast, damage=5)

    cycle = [repeater_blast, expel_blast]

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return charge_up
        return cycle[(turn - 1) % len(cycle)]

    return Enemy("Cubex Construct", 65, [charge_up, repeater_blast, expel_blast], choose)


def make_fogmog() -> Enemy:
    """Wiki: HP 74."""
    def _thwack(engine, enemy):
        dmg = enemy.deal_attack_damage(8)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.STRENGTH, 1)
    thwack = Move("Thwack", IntentType.ATTACK, _thwack, damage=8)
    headbutt = Move("Headbutt", IntentType.ATTACK, _dmg_move(14), damage=14)

    def _illusory_spores(engine, enemy):
        engine.summon_enemy(make_eye_with_teeth(), summoner=enemy)
    spores = Move("Illusory Spores", IntentType.BUFF, _illusory_spores, damage=0)
    cycle = [thwack, spores, headbutt]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    return Enemy("Fogmog", 74, cycle, choose)


def make_mawler() -> Enemy:
    """Wiki: HP 72."""
    rip_and_tear = Move("Rip and Tear", IntentType.ATTACK, _dmg_move(14), damage=14)

    def _roar(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.add_status(StatusType.VULNERABLE, 3)
        engine.log.append(f"{target.name} gains 3 Vulnerable ({enemy.name})")
    roar = Move("Roar", IntentType.DEBUFF, _roar, damage=0)

    def _claw(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(2):
            if not target.alive:
                break
            dmg = enemy.deal_attack_damage(4)
            target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
    claw = Move("Claw", IntentType.ATTACK, _claw, damage=4)

    cycle = [rip_and_tear, claw]

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return roar
        return cycle[(turn - 1) % len(cycle)]

    return Enemy("Mawler", 72, [rip_and_tear, roar, claw], choose)


def make_vine_shambler() -> Enemy:
    """Wiki: HP 61."""
    def _swipe(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(2):
            if not target.alive:
                break
            dmg = enemy.deal_attack_damage(6)
            target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
    swipe = Move("Swipe", IntentType.ATTACK, _swipe, damage=6)

    def _grasping_vines(engine, enemy):
        dmg = enemy.deal_attack_damage(8)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        target.add_status(StatusType.TANGLED, 1)
    grasping_vines = Move("Grasping Vines", IntentType.ATTACK_DEBUFF, _grasping_vines, damage=8)
    chomp = Move("Chomp", IntentType.ATTACK, _dmg_move(16), damage=16)

    cycle = [swipe, grasping_vines, chomp]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    return Enemy("Vine Shambler", 61, [swipe, grasping_vines, chomp], choose)


def make_flyconid() -> Enemy:
    """Wiki: HP 47-49."""
    def _weakening_spores(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.add_status(StatusType.VULNERABLE, 2)
        engine.log.append(f"{target.name} gains 2 Vulnerable ({enemy.name})")
    weakening_spores = Move("Weakening Spores", IntentType.DEBUFF, _weakening_spores, damage=0)

    def _frail_spores(engine, enemy):
        dmg = enemy.deal_attack_damage(8)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        target.add_status(StatusType.FRAIL, 2)
    frail_spores = Move("Frail Spores", IntentType.ATTACK_DEBUFF, _frail_spores, damage=8)
    smash = Move("Smash", IntentType.ATTACK, _dmg_move(11), damage=11)

    cycle = [frail_spores, smash]

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return weakening_spores
        return cycle[(turn - 1) % len(cycle)]

    hp = CONTENT_RNG.randint(47, 49)
    return Enemy("Flyconid", hp, [weakening_spores, frail_spores, smash], choose)


def make_slithering_strangler() -> Enemy:
    """Wiki: HP 53-55."""
    def _constrict(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.add_status(StatusType.CONSTRICT, 3)
        engine.log.append(f"{target.name} gains 3 Constrict ({enemy.name})")
    constrict = Move("Constrict", IntentType.DEBUFF, _constrict, damage=0)

    def _thwack(engine, enemy):
        dmg = enemy.deal_attack_damage(7)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        enemy.gain_block(5)
    thwack = Move("Thwack", IntentType.ATTACK, _thwack, damage=7)
    lash = Move("Lash", IntentType.ATTACK, _dmg_move(12), damage=12)

    cycle = [thwack, lash]

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return constrict
        return cycle[(turn - 1) % len(cycle)]

    hp = CONTENT_RNG.randint(53, 55)
    return Enemy("Slithering Strangler", hp, [constrict, thwack, lash], choose)


def make_snapping_jaxfruit() -> Enemy:
    """Wiki: HP 31-33. Single move: Energy Orb (3 dmg, gain 2 Strength)."""
    def _energy_orb(engine, enemy):
        dmg = enemy.deal_attack_damage(3)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.STRENGTH, 2)
    energy_orb = Move("Energy Orb", IntentType.ATTACK, _energy_orb, damage=3)

    def choose(enemy: Enemy, turn: int) -> Move:
        return energy_orb

    hp = CONTENT_RNG.randint(31, 33)
    return Enemy("Snapping Jaxfruit", hp, [energy_orb], choose)


def make_leaf_slime_small() -> Enemy:
    """Wiki: HP 11-15."""
    tackle = Move("Tackle", IntentType.ATTACK, _dmg_move(3), damage=3)

    def _goop(engine, enemy):
        target = engine.pick_enemy_attack_target()
        _shuffle_status_cards(engine, target, make_slimed, 1, "Slimed")
    goop = Move("Goop", IntentType.DEBUFF, _goop, damage=0)
    cycle = [tackle, goop]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[(turn + 1) % len(cycle)]

    hp = CONTENT_RNG.randint(11, 15)
    return Enemy("Leaf Slime (S)", hp, [tackle, goop], choose)


def make_leaf_slime_medium() -> Enemy:
    """Wiki: HP 32-35."""
    clump_shot = Move("Clump Shot", IntentType.ATTACK, _dmg_move(8), damage=8)

    def _sticky_shot(engine, enemy):
        target = engine.pick_enemy_attack_target()
        _shuffle_status_cards(engine, target, make_slimed, 2, "Slimed")
    sticky_shot = Move("Sticky Shot", IntentType.DEBUFF, _sticky_shot, damage=0)
    cycle = [clump_shot, sticky_shot]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[(turn + 1) % len(cycle)]

    hp = CONTENT_RNG.randint(32, 35)
    return Enemy("Leaf Slime (M)", hp, [clump_shot, sticky_shot], choose)


def make_twig_slime_small() -> Enemy:
    """Wiki: HP 7-11. Single move: Tackle (4 dmg)."""
    tackle = Move("Tackle", IntentType.ATTACK, _dmg_move(4), damage=4)

    def choose(enemy: Enemy, turn: int) -> Move:
        return tackle

    hp = CONTENT_RNG.randint(7, 11)
    return Enemy("Twig Slime (S)", hp, [tackle], choose)


def make_twig_slime_medium() -> Enemy:
    """Wiki: HP 26-28."""
    chomp = Move("Chomp", IntentType.ATTACK, _dmg_move(11), damage=11)

    def _sticky_shot(engine, enemy):
        target = engine.pick_enemy_attack_target()
        _shuffle_status_cards(engine, target, make_slimed, 1, "Slimed")
    sticky_shot = Move("Sticky Shot", IntentType.DEBUFF, _sticky_shot, damage=0)
    cycle = [chomp, sticky_shot]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[(turn + 1) % len(cycle)]

    hp = CONTENT_RNG.randint(26, 28)
    return Enemy("Twig Slime (M)", hp, [chomp, sticky_shot], choose)


def make_wriggler() -> Enemy:
    """Wiki: HP 17-21."""
    nasty_bite = Move("Nasty Bite", IntentType.ATTACK, _dmg_move(6), damage=6)

    def _wriggle(engine, enemy):
        target = engine.pick_enemy_attack_target()
        _shuffle_status_cards(engine, target, make_infection, 1, "Infection")
        enemy.add_status(StatusType.STRENGTH, 2)
    wriggle = Move("Wriggle", IntentType.DEBUFF, _wriggle, damage=0)
    cycle = [nasty_bite, wriggle]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[(turn + 1) % len(cycle)]

    hp = CONTENT_RNG.randint(17, 21)
    return Enemy("Wriggler", hp, [nasty_bite, wriggle], choose)


def make_bygone_effigy() -> Enemy:
    """Wiki: Elite, HP 127."""
    sleep = Move("Sleep", IntentType.BUFF, _nothing, damage=0)

    def _wake(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 10)
        engine.log.append(f"{enemy.name} wakes up and gains 10 Strength")
    wake = Move("Wake", IntentType.BUFF, _wake, damage=0)
    slashes = Move("Slashes", IntentType.ATTACK, _dmg_move(13), damage=13)

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return sleep
        if turn == 1:
            return wake
        return slashes

    return Enemy("Bygone Effigy", 127, [sleep, wake, slashes], choose, category="elite")


def make_phrog_parasite() -> Enemy:
    """Wiki: Elite, HP 61-64."""
    def _infect(engine, enemy):
        target = engine.pick_enemy_attack_target()
        _shuffle_status_cards(engine, target, make_infection, 3, "Infection")
    infect = Move("Infect", IntentType.DEBUFF, _infect, damage=0)

    def _lash(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(4):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(4), log=engine.log,
                                label=enemy.name, attacker=enemy)
    lash = Move("Lash", IntentType.ATTACK, _lash, damage=4)
    cycle = [infect, lash]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    def _infested(engine, enemy):
        engine.summon_enemy([make_wriggler() for _ in range(4)],
                             summoner=enemy, stunned=True)

    e = Enemy("Phrog Parasite", CONTENT_RNG.randint(61, 64), cycle, choose, category="elite")
    e.on_death = _infested
    return e


def make_ceremonial_beast() -> Enemy:
    """Wiki: Boss, HP 252, two phases."""
    def _stamp(engine, enemy):
        enemy.add_status(StatusType.PLOW, 150)
        engine.log.append(f"{enemy.name} gains Plow 150 (phase 2 at 150 HP)")
    stamp = Move("Stamp", IntentType.BUFF, _stamp, damage=0)

    def _plow(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(18), log=engine.log,
                            label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.STRENGTH, 2)
    plow = Move("Plow", IntentType.ATTACK, _plow, damage=18)
    stun = Move("Stun", IntentType.BUFF, _nothing, damage=0)

    def _beast_cry(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.RINGING, 1, applier=enemy)
        engine.log.append(f"{enemy.name} applies 1 Ringing (only 1 card next turn)")
    beast_cry = Move("Beast Cry", IntentType.DEBUFF, _beast_cry, damage=0)
    stomp = Move("Stomp", IntentType.ATTACK, _dmg_move(15), damage=15)

    def _crush(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(17), log=engine.log,
                            label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.STRENGTH, 3)
    crush = Move("Crush", IntentType.ATTACK, _crush, damage=17)
    phase2 = [beast_cry, stomp, crush]

    def choose(enemy: Enemy, turn: int) -> Move:
        threshold = enemy.get_status(StatusType.PLOW)
        broken = getattr(enemy, "plow_broken", False)
        if threshold and not broken and enemy.hp <= threshold:
            enemy.plow_broken = True
            enemy.phase2_turn = 0
            enemy.statuses.pop(StatusType.STRENGTH, None)
            return stun
        if broken:
            i = getattr(enemy, "phase2_turn", 0)
            enemy.phase2_turn = i + 1
            return phase2[i % len(phase2)]
        return stamp if turn == 0 else plow

    return Enemy("Ceremonial Beast", 252, [stamp, plow, stun] + phase2,
                  choose, category="boss")


def make_the_kin() -> List[Enemy]:
    """Wiki: Overgrowth boss "The Kin" -- one Kin Priest (190 HP) and TWO Kin Followers (58-59 each)..."""
    def _orb(name, dmg, status, amount):
        def _resolve(engine, enemy):
            target = engine.pick_enemy_attack_target()
            target.take_damage(enemy.deal_attack_damage(dmg), log=engine.log,
                                label=enemy.name, attacker=enemy)
            target.add_status(status, amount, applier=enemy)
        return Move(name, IntentType.ATTACK, _resolve, damage=dmg)

    orb_frailty = _orb("Orb of Frailty", 8, StatusType.FRAIL, 1)
    orb_weakness = _orb("Orb of Weakness", 8, StatusType.WEAK, 1)

    def _soul_beam(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(3):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(3), log=engine.log,
                                label=enemy.name, attacker=enemy)
    soul_beam = Move("Soul Beam", IntentType.ATTACK, _soul_beam, damage=3)

    def _dark_ritual(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    dark_ritual = Move("Dark Ritual", IntentType.BUFF, _dark_ritual, damage=0)

    priest_cycle = [orb_frailty, orb_weakness, soul_beam, dark_ritual]

    def priest_choose(enemy: Enemy, turn: int) -> Move:
        return priest_cycle[turn % len(priest_cycle)]

    priest = Enemy("Kin Priest", 190, list(priest_cycle), priest_choose, category="boss")

    quick_slash = Move("Quick Slash", IntentType.ATTACK, _dmg_move(5), damage=5)

    def _boomerang(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(2):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(2), log=engine.log,
                                label=enemy.name, attacker=enemy)
    boomerang = Move("Boomerang", IntentType.ATTACK, _boomerang, damage=2)

    def _power_dance(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    power_dance = Move("Power Dance", IntentType.BUFF, _power_dance, damage=0)

    follower_cycle = [quick_slash, boomerang, power_dance]

    def _make_follower_choose(offset):
        def choose(enemy: Enemy, turn: int) -> Move:
            return follower_cycle[(turn + offset) % len(follower_cycle)]
        return choose

    units = [priest]
    for offset in (0, 2):
        f = Enemy("Kin Follower", CONTENT_RNG.randint(58, 59), list(follower_cycle),
                   _make_follower_choose(offset), category="boss")
        f.is_minion = True
        f.leader = priest
        units.append(f)
    return units
