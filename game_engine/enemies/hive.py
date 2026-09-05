"""Act 2, the Hive."""

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


def make_bowlbug_rock() -> Enemy:
    """Wiki: HP 45-48."""
    headbutt = Move("Headbutt", IntentType.ATTACK, _dmg_move(15), damage=15)
    dizzy = Move("Dizzy", IntentType.BUFF, _nothing, damage=0)
    cycle = [headbutt, dizzy]
    return _bowlbug("Bowlbug (Rock)", (45, 48), cycle,
                     lambda e, t: cycle[t % 2])


def make_bowlbug_egg() -> Enemy:
    """Wiki: HP 21-22. Bite (7 dmg, gains 7 Block) -- its only move."""
    def _bite(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(7), log=engine.log,
                            label=enemy.name, attacker=enemy)
        enemy.gain_block(7)
    bite = Move("Bite", IntentType.ATTACK, _bite, damage=7)
    return _bowlbug("Bowlbug (Egg)", (21, 22), [bite], lambda e, t: bite)


def make_bowlbug_silk() -> Enemy:
    """Wiki: HP 40-43. Thrash (4 dmg x2); Spin Web (applies 1 Weak)."""
    thrash = Move("Thrash", IntentType.ATTACK, _multi_hit(4, 2), damage=4)

    def _spin_web(engine, enemy):
        engine.pick_enemy_attack_target().add_status(StatusType.WEAK, 1, applier=enemy)
    spin_web = Move("Spin Web", IntentType.DEBUFF, _spin_web, damage=0)
    cycle = [thrash, spin_web]
    return _bowlbug("Bowlbug (Silk)", (40, 43), cycle, lambda e, t: cycle[t % 2])


def make_bowlbug_nectar() -> Enemy:
    """Wiki: HP 35-38."""
    thrash = Move("Thrash", IntentType.ATTACK, _dmg_move(3), damage=3)

    def _buff(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 15)
        engine.log.append(f"{enemy.name} gains 15 Strength")
    buff = Move("Buff", IntentType.BUFF, _buff, damage=0)
    cycle = [thrash, buff]
    return _bowlbug("Bowlbug (Nectar)", (35, 38), cycle, lambda e, t: cycle[t % 2])


def make_chomper() -> Enemy:
    """Wiki: HP 60-64. Clamp (8 dmg x2); Screech (shuffles 3 Dazed)."""
    clamp = Move("Clamp", IntentType.ATTACK, _multi_hit(8, 2), damage=8)

    def _screech(engine, enemy):
        _shuffle_status_cards(engine, engine.pick_enemy_attack_target(),
                               make_dazed, 3, "Dazed")
    screech = Move("Screech", IntentType.DEBUFF, _screech, damage=0)
    cycle = [clamp, screech]
    return Enemy("Chomper", CONTENT_RNG.randint(60, 64), cycle, lambda e, t: cycle[t % 2])


def make_exoskeleton() -> Enemy:
    """Wiki: HP 24-28."""
    skitter = Move("Skitter", IntentType.ATTACK, _multi_hit(1, 3), damage=1)
    mandibles = Move("Mandibles", IntentType.ATTACK, _dmg_move(8), damage=8)

    def _enrage(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    enrage = Move("Enrage", IntentType.BUFF, _enrage, damage=0)
    cycle = [skitter, mandibles, enrage]
    return Enemy("Exoskeleton", CONTENT_RNG.randint(24, 28), cycle,
                  lambda e, t: cycle[t % 3])


def make_hunter_killer() -> Enemy:
    """Wiki: HP 121."""
    def _goop(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.TENDER, 1, applier=enemy)
        engine.log.append(f"{enemy.name} applies 1 Tender")
    goop = Move("Tenderizing Goop", IntentType.DEBUFF, _goop, damage=0)
    bite = Move("Bite", IntentType.ATTACK, _dmg_move(17), damage=17)
    puncture = Move("Puncture", IntentType.ATTACK, _multi_hit(7, 3), damage=7)
    after = [puncture, bite, puncture]

    def choose(enemy: Enemy, turn: int) -> Move:
        return goop if turn == 0 else after[(turn - 1) % len(after)]

    return Enemy("Hunter Killer", 121, [goop, bite, puncture], choose)


def make_louse_progenitor() -> Enemy:
    """Wiki: HP 134-136."""
    def _web_rider(engine, enemy, target):
        target.add_status(StatusType.FRAIL, 2, applier=enemy)
    web_cannon = Move("Web Cannon", IntentType.ATTACK, _multi_hit(9, 1, _web_rider), damage=9)

    def _curl(engine, enemy):
        enemy.gain_block(14)
        enemy.add_status(StatusType.STRENGTH, 5)
    curl = Move("Curl and Grow", IntentType.DEFEND, _curl, damage=0)
    pounce = Move("Pounce", IntentType.ATTACK, _dmg_move(14), damage=14)
    cycle = [web_cannon, curl, pounce]
    return Enemy("Louse Progenitor", CONTENT_RNG.randint(134, 136), cycle,
                  lambda e, t: cycle[t % 3])


def make_mysterious_knight() -> Enemy:
    """Wiki: HP 101."""
    def _breaker(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 3)
    breaker = Move("Breaker", IntentType.BUFF, _breaker, damage=0)
    flail = Move("Flail", IntentType.ATTACK, _multi_hit(9, 2), damage=9)
    ram = Move("Ram", IntentType.ATTACK, _dmg_move(15), damage=15)
    cycle = [breaker, flail, ram]
    return Enemy("Mysterious Knight", 101, cycle, lambda e, t: cycle[t % 3])


def make_myte() -> Enemy:
    """Wiki: HP 61-67."""
    def _cornucopia(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(2):
            target.add_to_hand(make_toxic(), engine.log)
        engine.log.append(f"{target.name} gains 2 Toxic in hand ({enemy.name})")
    cornucopia = Move("Toxic Cornucopia", IntentType.DEBUFF, _cornucopia, damage=0)
    bite = Move("Bite", IntentType.ATTACK, _dmg_move(13), damage=13)

    def _suck_rider(engine, enemy, target):
        enemy.add_status(StatusType.STRENGTH, 2)
    suck = Move("Suck", IntentType.ATTACK, _multi_hit(4, 1, _suck_rider), damage=4)
    cycle = [cornucopia, bite, suck]
    return Enemy("Myte", CONTENT_RNG.randint(61, 67), cycle, lambda e, t: cycle[t % 3])


def make_ovicopter() -> Enemy:
    """Wiki: HP 124-130."""
    def _lay_eggs(engine, enemy):
        engine.summon_enemy([make_tough_egg() for _ in range(3)], summoner=enemy)
    lay_eggs = Move("Lay Eggs", IntentType.BUFF, _lay_eggs, damage=0)
    smash = Move("Smash", IntentType.ATTACK, _dmg_move(16), damage=16)

    def _vuln_rider(engine, enemy, target):
        target.add_status(StatusType.VULNERABLE, 2, applier=enemy)
    tenderizer = Move("Tenderizer", IntentType.ATTACK, _multi_hit(7, 1, _vuln_rider), damage=7)

    def _paste(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 3)
    paste = Move("Nutritional Paste", IntentType.BUFF, _paste, damage=0)
    cycle = [lay_eggs, tenderizer, smash, paste]
    return Enemy("Ovicopter", CONTENT_RNG.randint(124, 130), cycle,
                  lambda e, t: cycle[t % 4])


def make_slumbering_beetle() -> Enemy:
    """Wiki: HP 86."""
    snore = Move("Snore", IntentType.BUFF, _nothing, damage=0)

    def _roll_rider(engine, enemy, target):
        enemy.add_status(StatusType.STRENGTH, 2)
    roll_out = Move("Roll Out", IntentType.ATTACK, _multi_hit(16, 1, _roll_rider), damage=16)

    def choose(enemy: Enemy, turn: int) -> Move:
        return snore if turn == 0 else roll_out

    return Enemy("Slumbering Beetle", 86, [snore, roll_out], choose)


def make_spiny_toad() -> Enemy:
    """Wiki: HP 116-119."""
    def _spikes(engine, enemy):
        enemy.add_status(StatusType.THORNS, 5)
        engine.log.append(f"{enemy.name} gains 5 Thorns")
    spikes = Move("Protruding Spikes", IntentType.BUFF, _spikes, damage=0)

    def _explosion(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(23), log=engine.log,
                            label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.THORNS, -5)
    explosion = Move("Spike Explosion", IntentType.ATTACK, _explosion, damage=23)
    tongue = Move("Tongue Lash", IntentType.ATTACK, _dmg_move(17), damage=17)
    cycle = [spikes, tongue, explosion]
    return Enemy("Spiny Toad", CONTENT_RNG.randint(116, 119), cycle,
                  lambda e, t: cycle[t % 3])


def make_the_obscura() -> Enemy:
    """Wiki: HP 123."""
    def _illusion(engine, enemy):
        engine.summon_enemy(make_parafright(), summoner=enemy)
    illusion = Move("Illusion", IntentType.BUFF, _illusion, damage=0)
    gaze = Move("Piercing Gaze", IntentType.ATTACK, _dmg_move(10), damage=10)

    def _wail(engine, enemy):
        for e in engine.enemies_alive():
            e.add_status(StatusType.STRENGTH, 3)
        engine.log.append(f"{enemy.name} wails: ALL enemies gain 3 Strength")
    wail = Move("Wail", IntentType.BUFF, _wail, damage=0)

    def _harden_rider(engine, enemy, target):
        enemy.gain_block(6)
    hardening = Move("Hardening Strike", IntentType.ATTACK,
                      _multi_hit(6, 1, _harden_rider), damage=6)
    cycle = [illusion, gaze, wail, hardening]
    return Enemy("The Obscura", 123, cycle, lambda e, t: cycle[t % 4])


def make_thieving_hopper() -> Enemy:
    """Wiki: HP 79."""
    def _thievery(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(17), log=engine.log,
                            label=enemy.name, attacker=enemy)
        if target.draw_pile:
            stolen = target.draw_pile.pop()
            enemy.stolen_cards.append((target, stolen))
            engine.log.append(f"{enemy.name} steals {stolen.name}")
    thievery = Move("Thievery", IntentType.ATTACK, _thievery, damage=17)

    def _flutter(engine, enemy):
        enemy.add_status(StatusType.FLUTTER, 5)
        engine.log.append(f"{enemy.name} gains Flutter (50% less attack damage, 5 hits)")
    flutter = Move("Flutter", IntentType.DEFEND, _flutter, damage=0)
    hat_trick = Move("Hat Trick", IntentType.ATTACK, _dmg_move(21), damage=21)
    nab = Move("Nab", IntentType.ATTACK, _dmg_move(14), damage=14)

    def _escape(engine, enemy):
        enemy.alive = False
        enemy.death_resolved = True
        engine.log.append(
            f"{enemy.name} escapes with {len(enemy.stolen_cards)} stolen card(s)")
    escape = Move("Escape", IntentType.BUFF, _escape, damage=0)
    cycle = [thievery, flutter, nab, hat_trick, escape]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    def _on_death(engine, enemy):
        for owner, card in enemy.stolen_cards:
            owner.discard_pile.append(card)
        if enemy.stolen_cards:
            engine.log.append(f"{len(enemy.stolen_cards)} stolen card(s) recovered")
        enemy.stolen_cards = []

    e = Enemy("Thieving Hopper", 79, cycle, choose)
    e.stolen_cards = []
    e.on_death = _on_death
    return e


def make_tunneler() -> Enemy:
    """Wiki: HP 87."""
    bite = Move("Bite", IntentType.ATTACK, _dmg_move(13), damage=13)

    def _burrow(engine, enemy):
        enemy.add_status(StatusType.BURROWED, 1)
        enemy.gain_block(32)
        engine.log.append(f"{enemy.name} burrows and gains 32 Block")
    burrow = Move("Burrow", IntentType.DEFEND, _burrow, damage=0)
    below = Move("Attack from Below", IntentType.ATTACK, _dmg_move(23), damage=23)

    def _emerge(engine, enemy):
        enemy.statuses.pop(StatusType.BURROWED, None)
        engine.log.append(f"{enemy.name} is forced out of the ground")
    emerging = Move("Emerging Strike", IntentType.BUFF, _emerge, damage=0)

    def choose(enemy: Enemy, turn: int) -> Move:
        if enemy.has_status(StatusType.BURROWED):
            return emerging if enemy.block <= 0 else below
        return bite if turn == 0 or getattr(enemy, "just_emerged", False) else burrow

    return Enemy("Tunneler", 87, [bite, burrow, below, emerging], choose)


def make_decimillipede_group() -> List[Enemy]:
    """Wiki: Elite, THREE segments of 40-46 HP each, staggered across the same 3-move cycle: Bulk (6..."""
    def _bulk_rider(engine, enemy, target):
        enemy.add_status(StatusType.STRENGTH, 2)
    bulk = Move("Bulk", IntentType.ATTACK, _multi_hit(6, 1, _bulk_rider), damage=6)
    writhe = Move("Writhe", IntentType.ATTACK, _multi_hit(5, 2), damage=5)

    def _weak_rider(engine, enemy, target):
        target.add_status(StatusType.WEAK, 1, applier=enemy)
    outgas = Move("Outgas", IntentType.ATTACK, _multi_hit(8, 1, _weak_rider), damage=8)
    cycle = [bulk, writhe, outgas]

    def _make_choose(offset):
        def choose(enemy: Enemy, turn: int) -> Move:
            if getattr(enemy, "reattached", False):
                enemy.reattached = False
                return enemy.rng.choice(cycle)
            return cycle[(turn + offset) % len(cycle)]
        return choose

    def _schedule_reattach(engine, enemy):
        """Powers module: "if other segments are still alive, revives in 2 turns with X HP." The 2-turn..."""
        others = [e for e in engine.enemies
                  if e.alive and e.name == "Decimillipede" and e is not enemy]
        if not others:
            return
        enemy.revive_in = 2
        engine.log.append(f"{enemy.name} will reattach in 2 turns")

    def _reattach(engine, enemy):
        others = [e for e in engine.enemies
                  if e.alive and e.name == "Decimillipede" and e is not enemy]
        if not others:
            return
        enemy.alive = True
        enemy.hp = 25
        enemy.death_resolved = False
        enemy.reattached = True
        engine.log.append(f"{enemy.name} reattaches and revives with 25 HP")

    segments = []
    for offset in range(3):
        seg = Enemy("Decimillipede", CONTENT_RNG.randint(40, 46), list(cycle),
                     _make_choose(offset), category="elite")
        seg.on_death = _schedule_reattach
        seg.on_revive = _reattach
        segments.append(seg)
    return segments


def make_entomancer() -> Enemy:
    """Wiki: Elite, HP 145."""
    beees = Move("Beeeees!", IntentType.ATTACK, _multi_hit(3, 7), damage=3)
    spear = Move("Spear!", IntentType.ATTACK, _dmg_move(18), damage=18)

    def _pheromone(engine, enemy):
        enemy.add_status(StatusType.PERSONAL_HIVE, 1)
        enemy.add_status(StatusType.STRENGTH, 1)
        engine.log.append(f"{enemy.name} gains 1 Personal Hive and 1 Strength")
    pheromone = Move("Pheromone Spit", IntentType.BUFF, _pheromone, damage=0)
    cycle = [pheromone, beees, spear]
    return Enemy("Entomancer", 145, cycle, lambda e, t: cycle[t % 3], category="elite")


def make_infested_prism() -> Enemy:
    """Wiki: Elite, HP 161."""
    jab = Move("Jab", IntentType.ATTACK, _dmg_move(15), damage=15)

    def _block_rider(amount):
        def rider(engine, enemy, target):
            enemy.gain_block(amount)
        return rider
    radiate = Move("Radiate", IntentType.ATTACK, _multi_hit(11, 1, _block_rider(16)), damage=11)
    whirlwind = Move("Whirlwind", IntentType.ATTACK, _multi_hit(5, 3), damage=5)
    pulsate = Move("Pulsate", IntentType.ATTACK, _multi_hit(8, 1, _block_rider(20)), damage=8)
    cycle = [jab, radiate, whirlwind, pulsate]
    return Enemy("Infested Prism", 161, cycle, lambda e, t: cycle[t % 4], category="elite")


def make_the_insatiable() -> Enemy:
    """Wiki: Boss, HP 321."""
    def _liquify(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.SANDPIT, 4, applier=enemy)
            for _ in range(3):
                p.draw_pile.insert(0, make_frantic_escape())
                p.discard_pile.append(make_frantic_escape())
        engine.log.append(f"{enemy.name} liquifies the ground: 4 Sandpit and 6 Frantic Escape")
    liquify = Move("Liquify Ground", IntentType.DEBUFF, _liquify, damage=0)
    thrash = Move("Thrash", IntentType.ATTACK, _multi_hit(8, 2), damage=8)
    lunging = Move("Lunging Bite", IntentType.ATTACK, _dmg_move(28), damage=28)

    def _salivate(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    salivate = Move("Salivate", IntentType.BUFF, _salivate, damage=0)
    after = [thrash, lunging, salivate, thrash]

    def choose(enemy: Enemy, turn: int) -> Move:
        return liquify if turn == 0 else after[(turn - 1) % len(after)]

    return Enemy("The Insatiable", 321,
                  [liquify, thrash, lunging, salivate], choose, category="boss")


def make_knowledge_demon() -> Enemy:
    """Wiki: Boss, HP 379."""
    def _curse(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.WEAK, 2, applier=enemy)
        engine.log.append(f"{enemy.name} forces a choice of debuff (auto-picked Weak)")
    curse = Move("Curse of Knowledge", IntentType.DEBUFF, _curse, damage=0)
    slap = Move("Slap", IntentType.ATTACK, _dmg_move(17), damage=17)
    overwhelming = Move("Knowledge Overwhelming", IntentType.ATTACK,
                         _multi_hit(8, 3), damage=8)

    def _ponder(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(11), log=engine.log,
                            label=enemy.name, attacker=enemy)
        healed = 30 * len(engine.players)
        enemy.heal(healed)
        enemy.add_status(StatusType.STRENGTH, 2)
        engine.log.append(f"{enemy.name} heals {healed} HP (30 per player)")
    ponder = Move("Ponder", IntentType.ATTACK, _ponder, damage=11)
    cycle = [curse, slap, overwhelming, ponder]
    return Enemy("Knowledge Demon", 379, cycle, lambda e, t: cycle[t % 4],
                  category="boss")


def make_kaiser_crab() -> List[Enemy]:
    """Wiki: the Kaiser Crab boss fight is TWO units -- Crusher (209 HP) and Rocket (199 HP) -- not one."""
    thrash = Move("Thrash", IntentType.ATTACK, _dmg_move(12), damage=12)
    enlarging = Move("Enlarging Strike", IntentType.ATTACK, _dmg_move(4), damage=4)

    def _sting_rider(engine, enemy, target):
        target.add_status(StatusType.WEAK, 2, applier=enemy)
        target.add_status(StatusType.FRAIL, 2, applier=enemy)
    bug_sting = Move("Bug Sting", IntentType.ATTACK, _multi_hit(6, 2, _sting_rider), damage=6)

    def _adapt(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    adapt = Move("Adapt", IntentType.BUFF, _adapt, damage=0)

    def _guard_rider(engine, enemy, target):
        enemy.gain_block(18)
    guarded = Move("Guarded Strike", IntentType.ATTACK, _multi_hit(12, 1, _guard_rider), damage=12)
    crusher_cycle = [enlarging, adapt, bug_sting, thrash, guarded]
    crusher = Enemy("Crusher", 209, crusher_cycle,
                     lambda e, t: crusher_cycle[t % len(crusher_cycle)], category="boss")

    reticle = Move("Targeting Reticle", IntentType.ATTACK, _dmg_move(3), damage=3)
    beam = Move("Precision Beam", IntentType.ATTACK, _dmg_move(18), damage=18)

    def _charge(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    charge = Move("Charge Up", IntentType.BUFF, _charge, damage=0)
    laser = Move("Laser", IntentType.ATTACK, _dmg_move(31), damage=31)
    recharge = Move("Recharge", IntentType.BUFF, _nothing, damage=0)
    rocket_cycle = [reticle, charge, beam, laser, recharge]
    rocket = Enemy("Rocket", 199, rocket_cycle,
                    lambda e, t: rocket_cycle[t % len(rocket_cycle)], category="boss")
    return [crusher, rocket]
