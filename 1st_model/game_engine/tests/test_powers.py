# -*- coding: utf-8 -*-
"""Task #41: verify every status against Module:Powers/StS2_data/{Common,Debuff}, the authoritative..."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from game_engine.entities import Player
import game_engine.enemies as E
from game_engine.combat import CombatEngine
from game_engine.cards import CARD_POOL_IRONCLAD, make_starter_deck
from game_engine.statuses import StatusType

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  [{'ok' if ok else 'FAIL'}] {label}: got {got!r}, want {want!r}")
    if not ok:
        FAILS.append(label)


def card(name):
    for f in CARD_POOL_IRONCLAD:
        c = f()
        if c.name == name:
            return c
    for c in make_starter_deck():
        if c.name == name:
            return c
    raise KeyError(name)


def bag(hp=2000):
    e = E.make_nibbit()
    e.max_hp = e.hp = hp
    return e


def setup(enemies=None, hp=500):
    p = Player("Tester", hp, 99, deck=make_starter_deck())
    eng = CombatEngine([p], enemies or [bag()], seed=11, scale_enemies=False)
    eng.start_player_turn()
    p.energy = 99
    return eng, p, eng.enemies[0]


print("=" * 74)
print('Regen: "at the END of your turn, heal X HP, then reduce Regen by 1"')
print("=" * 74)
eng, p, e = setup([E.make_battle_friend_v1()])
p.hp = 100
p.add_status(StatusType.REGEN, 5)
check("no heal at the start of the turn", p.hp, 100)
eng.end_player_turn()
check("heals at END of turn", p.hp, 105)
check("...then Regen drops by 1", p.get_status(StatusType.REGEN), 4)
eng.run_enemy_turn(); eng.start_player_turn()
check("...and still nothing at the next start of turn", p.hp, 105)
eng.end_player_turn()
check("...healing the reduced amount next end of turn", p.hp, 109)

print()
print("=" * 74)
print('Ritual: "at the END of its turn, gains X Strength"')
print("=" * 74)
cultist = E.make_calcified_cultist()
eng, p, _ = setup([cultist])
eng.end_player_turn(); eng.run_enemy_turn()
check("Incantation grants 2 Ritual", cultist.get_status(StatusType.RITUAL), 2)
check("...and Ritual pays out at the END of that same turn",
      cultist.get_status(StatusType.STRENGTH), 2)
eng.start_player_turn(); eng.end_player_turn(); eng.run_enemy_turn()
check("...compounding each turn", cultist.get_status(StatusType.STRENGTH), 4)

print()
print("=" * 74)
print('Poison stays start-of-turn: "at the START of its turn, loses X HP"')
print("=" * 74)
eng, p, e = setup()
p.hp = 100
p.add_status(StatusType.POISON, 4)
p.block = 50
eng.end_player_turn()
check("no poison tick at end of turn", p.hp, 100)
eng.run_enemy_turn(); eng.start_player_turn()
check("poison bites at the START of the turn", p.hp, 96)
check("...then drops by 1", p.get_status(StatusType.POISON), 3)

print()
print("=" * 74)
print('Shrink: "attacks deal 30% less damage... after 3 turns"')
print("=" * 74)
beetle = E.make_shrinker_beetle()
eng, p, _ = setup([beetle])
eng.end_player_turn(); eng.run_enemy_turn()
check("Shrinker applies 3 turns of Shrink", p.get_status(StatusType.SHRINK), 3)
check("...cutting attack damage 30%", p.deal_attack_damage(10), 7)
for expected in (2, 1, 0):
    eng.start_player_turn(); eng.end_player_turn(); eng.run_enemy_turn()
    if p.get_status(StatusType.SHRINK) != expected:
        FAILS.append(f"Shrink decay to {expected}")
check("...and wearing off after 3 turns", p.get_status(StatusType.SHRINK), 0)
check("...restoring full damage", p.deal_attack_damage(10), 10)

print()
print("=" * 74)
print('Tangled: "Attacks cost an additional energy for 2 turns"')
print("=" * 74)
eng, p, e = setup()
strike, defend = card("Strike"), card("Defend")
check("baseline Attack cost", strike.current_cost(p), 1)
p.add_status(StatusType.TANGLED, 2)
check("Tangled adds 1 to Attacks", strike.current_cost(p), 2)
check("...but not to Skills", defend.current_cost(p), 1)
p.next_attack_free = True
check("...and a genuinely free Attack stays free", strike.current_cost(p), 0)
p.next_attack_free = False
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("...wearing off after 2 turns", strike.current_cost(p), 1)

print()
print("=" * 74)
print("Spot-check: the debuffs the module confirmed unchanged")
print("=" * 74)
eng, p, e = setup()
e.add_status(StatusType.VULNERABLE, 1)
check("Vulnerable: 50% more from Attacks", e.take_damage(10, log=eng.log, attacker=p).to_hp, 15)
eng, p, e = setup()
p.add_status(StatusType.WEAK, 1)
check("Weak: attacks deal 25% less", p.deal_attack_damage(8), 6)
eng, p, e = setup()
p.add_status(StatusType.FRAIL, 1)
p.block = 0
p.gain_block(8)
check("Frail: 25% less Block", p.block, 6)
eng, p, e = setup()
e.add_status(StatusType.PLATED_ARMOR, 5)
e.block = 0
e.apply_end_of_turn_gains(eng.log)
check("Plating: block at end of turn", e.block, 5)
e.decay_statuses_end_of_turn()
check("...reduced by 1 per turn", e.get_status(StatusType.PLATED_ARMOR), 4)

print()
print("=" * 74)
if FAILS:
    print(f"{len(FAILS)} FAILURE(S):")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("ALL POWER-MODULE CHECKS PASSED")
