# -*- coding: utf-8 -*-
"""Verification for Act 3 (Glory) and its new mechanics."""
import os
import sys

# The modules under test live one directory up. This used to be a hardcoded
# absolute path, which is why the whole suite only ran on one machine from
# one directory -- and why it lived in a temp folder rather than the repo.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from entities import Player
import enemies as E
from combat import CombatEngine
from cards import (CARD_POOL_IRONCLAD, make_starter_deck, make_burn,
                   make_wither, CardType)
from statuses import StatusType

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


def setup(enemies, hp=4000, act="act3"):
    p = Player("Tester", hp, 99, deck=make_starter_deck())
    eng = CombatEngine([p], enemies, seed=8, scale_enemies=False, act=act)
    eng.start_player_turn()
    p.energy = 99
    return eng, p


def enemy_turn(eng, p):
    eng.end_player_turn()
    eng.run_enemy_turn()
    if not eng.is_over:
        eng.start_player_turn()
        p.energy = 99
        p.block = 0


print("=" * 74)
print("Soar (Owl Magistrate)")
print("=" * 74)
owl = E.make_owl_magistrate()
eng, p = setup([owl])
for _ in range(2):
    enemy_turn(eng, p)
enemy_turn(eng, p)          # Judicial Flight
check("Judicial Flight grants Soar", owl.has_status(StatusType.SOAR), True)
hp0 = owl.hp
owl.take_damage(40, log=eng.log, attacker=p)
check("Soar halves attack damage", hp0 - owl.hp, 20)
check("...and spends no stack (unlike Flutter)", owl.has_status(StatusType.SOAR), True)
enemy_turn(eng, p)          # Verdict
check("Verdict lands and removes Soar", owl.has_status(StatusType.SOAR), False)
check("...and applies 4 Vulnerable", p.get_status(StatusType.VULNERABLE), 4)

print()
print("=" * 74)
print("Knight Gang: Hex and Downgraded")
print("=" * 74)
gang = E.make_knight_gang()
check("three knights", [e.name for e in gang], ["Flail Knight", "Spectral Knight", "Magi Knight"])
eng, p = setup(gang)
enemy_turn(eng, p)          # Spectral: Hex, Magi: Power Shield
check("Hex is applied", p.get_status(StatusType.HEX) > 0, True)
marked_a, marked_b = card("Strike"), card("Defend")
p.hand = [marked_a, marked_b]
before_exhaust = len(p.exhaust_pile)
eng.end_player_turn()
check("Hex makes the hand Ethereal (exhausts, not discards)",
      len(p.exhaust_pile) - before_exhaust, 2)
check("...so those exact cards never reach the discard pile",
      (marked_a in p.discard_pile, marked_b in p.discard_pile), (False, False))
spectral = gang[1]
spectral.hp = 1
spectral.take_damage(99, log=eng.log, attacker=p)
eng._check_victory_defeat()
check("Hex fades when the Spectral Knight dies", p.get_status(StatusType.HEX), 0)

gang = E.make_knight_gang()
eng, p = setup(gang)
magi = gang[2]
p.add_status(StatusType.DOWNGRADED, 1)
upgraded_strike = card("Strike")
upgraded_strike.upgrade()
enemy = gang[0]
hp0 = enemy.hp
p.hand = [upgraded_strike]
eng.play_card(p, upgraded_strike, target=enemy)
check("Downgraded resolves an upgraded card as its base printing", hp0 - enemy.hp, 6)
check("...without permanently un-upgrading it", upgraded_strike.upgraded, True)
magi.hp = 1
magi.take_damage(99, log=eng.log, attacker=p)
eng._check_victory_defeat()
check("Downgraded fades when the Magi Knight dies",
      p.get_status(StatusType.DOWNGRADED), 0)

print()
print("=" * 74)
print("Queen: Chains of Binding / Bound")
print("=" * 74)
units = E.make_queen()
check("Queen fights with one Amalgam",
      [e.name for e in units], ["Queen", "Torch Head Amalgam"])
eng, p = setup(units)
enemy_turn(eng, p)          # Puppet Strings
check("Puppet Strings sets Chains of Binding", p.chains_of_binding, 3)
p.hand = []
p.draw_pile = [card("Strike") for _ in range(5)]
p.cards_drawn_this_turn = 0
p.draw_cards(5, eng.log)
bound = [c for c in p.hand if c.bound]
check("the first 3 cards drawn are Bound", len(bound), 3)
first = eng.play_card(p, bound[0], target=units[0])
second = eng.play_card(p, bound[1], target=units[0])
unbound = next(c for c in p.hand if not c.bound)
third = eng.play_card(p, unbound, target=units[0])
check("only one Bound card can be played per turn",
      (first, second, third), (True, False, True))
eng.end_player_turn()
check("cards are un-Bound at end of turn",
      any(c.bound for c in p.hand + p.draw_pile + p.discard_pile), False)

print()
print("=" * 74)
print("Test Subject: three phases")
print("=" * 74)
ts = E.make_test_subject()
eng, p = setup([ts])
check("phase 1 starts at 100 HP", (ts.phase, ts.max_hp), (1, 100))
ts.hp = 1
ts.take_damage(99, log=eng.log, attacker=p)
eng._check_victory_defeat()
check("Adaptable revives it into phase 2 at 200 HP",
      (ts.alive, ts.phase, ts.hp), (True, 2, 200))
check("...and the fight is not over", eng.is_over, False)
check("phase 2 turns on Painful Stabs", ts.painful_stabs, 1)
before = len(p.discard_pile)
ts.take_damage(10, log=eng.log, attacker=p)
check("Painful Stabs adds a Wound on unblocked damage",
      len(p.discard_pile) - before, 1)
hp0 = p.hp
p.block = 0
enemy_turn(eng, p)
first_claw = hp0 - p.hp
hp0 = p.hp
p.block = 0
enemy_turn(eng, p)
check("Multi-Claw gains a hit each use", (hp0 - p.hp) > first_claw, True)
ts.hp = 1
ts.take_damage(99, log=eng.log, attacker=p)
eng._check_victory_defeat()
check("phase 3 at 300 HP", (ts.alive, ts.phase, ts.hp), (True, 3, 300))
ts.hp = 1
ts.take_damage(99, log=eng.log, attacker=p)
eng._check_victory_defeat()
check("phase 3 can be killed for good", ts.alive, False)
check("...which ends the fight", eng.victory, True)

print()
print("=" * 74)
print("Aeonglass escalation and Burn/Wither")
print("=" * 74)
aeon = E.make_aeonglass()
eng, p = setup([aeon])
for _ in range(3):
    enemy_turn(eng, p)      # Ebb, Eye Lasers, Increasing Intensity
def all_withers(pl):
    # Withers can be reshuffled into the draw pile or drawn, so count every pile.
    return [c for c in pl.hand + pl.draw_pile + pl.discard_pile + pl.exhaust_pile
            if c.name.startswith("Wither")]
withers = all_withers(p)
check("Increasing Intensity adds a Wither", len(withers), 1)
check("...and grants Strength", aeon.get_status(StatusType.STRENGTH), 2)
for _ in range(3):
    enemy_turn(eng, p)
withers = all_withers(p)
check("the second use escalates the card", "Wither+1" in [c.name for c in withers], True)
check("...and grants more Strength", aeon.get_status(StatusType.STRENGTH), 5)

eng, p = setup([E.make_scroll_of_biting()])
p.hand = [make_burn(), make_wither(0), make_wither(2)]
p.block = 0
hp0 = p.hp
eng.end_player_turn()
check("Burn 2 + Wither 3 + Wither+2 5 = 10 damage held at end of turn",
      hp0 - p.hp, 10)

print()
print("=" * 74)
print("Fabricator's bot factory, and Guardbot buffing it")
print("=" * 74)
fab = E.make_fabricator()
eng, p = setup([fab])
enemy_turn(eng, p)          # Fabricate
bots = [e.name for e in eng.enemies if e is not fab]
check("Fabricate summons two bots", len(bots), 2)
check("...one defensive, one aggressive",
      (bots[0] in ("Guardbot", "Noisebot"), bots[1] in ("Zapbot", "Stabbot")), (True, True))
gb = E.make_guardbot()
eng, p = setup([E.make_fabricator(), gb])
fab2 = eng.enemies[0]
fab2.block = 0
enemy_turn(eng, p)
check("Guardbot gives its Block to the Fabricator", fab2.block >= 15, True)

print()
print("=" * 74)
print("Coverage")
print("=" * 74)
import play
glory = [k for k, (name, _) in play.ENCOUNTERS.items() if "[Glory" in name]
check("Glory encounters registered", len(glory), 17)
check("total encounters", len(play.ENCOUNTERS), 93)

print()
print("=" * 74)
if FAILS:
    print(f"{len(FAILS)} FAILURE(S):")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("ALL ACT 3 CHECKS PASSED")
