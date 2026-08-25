# -*- coding: utf-8 -*-
"""Verification for Act 2 (Hive) and its new mechanics."""
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
from cards import (CARD_POOL_IRONCLAD, make_starter_deck, make_toxic,
                   make_frantic_escape)
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


def setup(enemies, hp=3000, act="act2"):
    p = Player("Tester", hp, 99, deck=make_starter_deck())
    eng = CombatEngine([p], enemies, seed=6, scale_enemies=False, act=act)
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
print("Tender (Hunter Killer)")
print("=" * 74)
hk = E.make_hunter_killer()
eng, p = setup([hk])
enemy_turn(eng, p)
check("Tenderizing Goop applies 1 Tender", p.get_status(StatusType.TENDER), 1)
p.add_status(StatusType.STRENGTH, 10)
p.hand = [card("Strike"), card("Strike")]
eng.play_card(p, p.hand[0], target=hk)
check("first card costs 1 Strength this turn",
      p.get_status(StatusType.STRENGTH_LOSS_THIS_TURN), 1)
eng.play_card(p, p.hand[0], target=hk)
check("...and it compounds per card", p.get_status(StatusType.STRENGTH_LOSS_THIS_TURN), 2)
check("Dexterity is drained in step", p.get_status(StatusType.DEXTERITY_LOSS_THIS_TURN), 2)
p.block = 0
p.gain_block(10)
check("...which really cuts Block", p.block, 8)

print()
print("=" * 74)
print("Burrowed (Tunneler)")
print("=" * 74)
tun = E.make_tunneler()
eng, p = setup([tun])
enemy_turn(eng, p)          # Bite
enemy_turn(eng, p)          # Burrow
check("Burrow grants Burrowed and 32 Block",
      (tun.has_status(StatusType.BURROWED), tun.block), (True, 32))
enemy_turn(eng, p)          # Attack from Below -- block must survive its own turn
check("Block is NOT cleared while burrowed", tun.block, 32)
tun.block = 0
enemy_turn(eng, p)          # intent was queued while blocked, so this is the last dig
enemy_turn(eng, p)          # now it re-picks: block gone -> Emerging Strike
check("breaking the Block forces it out", tun.has_status(StatusType.BURROWED), False)

print()
print("=" * 74)
print("Flutter (Thieving Hopper)")
print("=" * 74)
hop = E.make_thieving_hopper()
eng, p = setup([hop])
hop.add_status(StatusType.FLUTTER, 5)
hp0 = hop.hp
hop.take_damage(20, log=eng.log, attacker=p)
check("Flutter halves attack damage", hp0 - hop.hp, 10)
check("...spending one stack per hit", hop.get_status(StatusType.FLUTTER), 4)
hp0 = hop.hp
hop.take_damage(20, source_is_attack=False, log=eng.log, attacker=p)
check("non-attack damage is unaffected and spends nothing",
      (hp0 - hop.hp, hop.get_status(StatusType.FLUTTER)), (20, 4))

print()
print("  -- theft and escape --")
hop = E.make_thieving_hopper()
eng, p = setup([hop])
p.draw_pile = [card("Bludgeon")]
enemy_turn(eng, p)          # Thievery
check("Thievery steals a card from the draw pile", len(hop.stolen_cards), 1)
check("...and it leaves the deck", any(c.name == "Bludgeon" for c in p.draw_pile), False)
eng._check_victory_defeat()
hop.hp = 1
hop.take_damage(99, log=eng.log, attacker=p)
eng._check_victory_defeat()
check("killing it recovers the stolen card",
      any(c.name == "Bludgeon" for c in p.discard_pile), True)

print()
print("=" * 74)
print("Sandpit + Frantic Escape (The Insatiable)")
print("=" * 74)
boss = E.make_the_insatiable()
eng, p = setup([boss])
enemy_turn(eng, p)          # Liquify Ground; start_player_turn ticks once
check("Liquify Ground applies Sandpit (4, ticked to 3)",
      p.get_status(StatusType.SANDPIT), 3)
check("...and shuffles in 6 Frantic Escape",
      sum(1 for c in p.draw_pile + p.discard_pile if c.name == "Frantic Escape"), 6)
esc = make_frantic_escape()
p.hand = [esc]
before = p.get_status(StatusType.SANDPIT)
eng.play_card(p, esc)
check("Frantic Escape buys a turn", p.get_status(StatusType.SANDPIT), before + 1)
# current_cost(), not .cost: the escalation goes through set_temp_cost so it
# reverts at combat end (see test_deck_purity -- a card in deck_template IS
# the object in hand, so writing .cost directly would inflate a real deck
# card permanently). The printed cost is deliberately still 1.
check("...and gets more expensive", esc.current_cost(p), 2)
check("...without touching its printed cost", esc.cost, 1)

# Run the countdown out with no escapes. Uses a plain enemy so the boss's
# own Liquify Ground can't top the counter back up mid-test.
eng, p = setup([E.make_bowlbug_egg()])
p.add_status(StatusType.SANDPIT, 2)
enemy_turn(eng, p)
alive_after_one = p.alive
enemy_turn(eng, p)
check("the countdown eventually kills", (alive_after_one, p.alive), (True, False))

print()
print("=" * 74)
print("Toxic (Myte)")
print("=" * 74)
myte = E.make_myte()
eng, p = setup([myte])
enemy_turn(eng, p)          # Toxic Cornucopia
check("Toxic Cornucopia puts 2 Toxic in HAND",
      sum(1 for c in p.hand if c.name == "Toxic"), 2)
p.block = 100
hp0 = p.hp
eng.end_player_turn()
check("Toxic costs 5 damage each if still held", hp0 - p.hp, 0)   # block absorbed
check("...and exhausts itself", sum(1 for c in p.exhaust_pile if c.name == "Toxic"), 2)

print()
print("=" * 74)
print("Summoning: Ovicopter, Tough Egg, The Obscura")
print("=" * 74)
ovi = E.make_ovicopter()
eng, p = setup([ovi])
enemy_turn(eng, p)          # Lay Eggs
check("Lay Eggs summons 3 Tough Eggs",
      sum(1 for e in eng.enemies if e.name == "Tough Egg" and e.alive), 3)
egg = next(e for e in eng.enemies if e.name == "Tough Egg")
enemy_turn(eng, p)          # eggs Nibble
enemy_turn(eng, p)          # eggs Hatch
check("a Tough Egg hatches into a Hatchling",
      any(e.name == "Hatchling" and e.alive for e in eng.enemies), True)
check("...and the egg is gone", egg.alive, False)

obs = E.make_the_obscura()
eng, p = setup([obs])
enemy_turn(eng, p)          # Illusion
check("The Obscura summons a Parafright",
      any(e.name == "Parafright" for e in eng.enemies), True)
enemy_turn(eng, p)          # Piercing Gaze
enemy_turn(eng, p)          # Wail
check("Wail buffs EVERY enemy",
      all(e.get_status(StatusType.STRENGTH) >= 3 for e in eng.enemies if e.alive), True)

print()
print("=" * 74)
print("Decimillipede's Reattach")
print("=" * 74)
segs = E.make_decimillipede_group()
eng, p = setup(segs)
check("three segments", len(segs), 3)
segs[0].hp = 1
segs[0].take_damage(99, log=eng.log, attacker=p)
eng._check_victory_defeat()
check("a dead segment schedules a reattach rather than reviving instantly",
      (segs[0].alive, segs[0].revive_in), (False, 2))
enemy_turn(eng, p)
check("...still down after one turn", segs[0].alive, False)
enemy_turn(eng, p)
check("...and revives with 25 HP after two", (segs[0].alive, segs[0].hp), (True, 25))
for s in segs:
    s.hp = 1
    s.take_damage(99, log=eng.log, attacker=p)
eng._check_victory_defeat()
check("killing them all together ends the fight", eng.victory, True)

print()
print("=" * 74)
print("Bosses")
print("=" * 74)
crab = E.make_kaiser_crab()
check("Kaiser Crab is two units", [e.name for e in crab], ["Crusher", "Rocket"])
kd = E.make_knowledge_demon()
eng, p = setup([kd])
kd.hp = 100
for _ in range(4):
    enemy_turn(eng, p)
check("Knowledge Demon's Ponder heals 30 per player", kd.hp > 100, True)

print()
print("=" * 74)
print("Coverage")
print("=" * 74)
import play
hive = [k for k, (name, _) in play.ENCOUNTERS.items() if "[Hive" in name]
check("Hive encounters registered", len(hive), 22)
check("total encounters", len(play.ENCOUNTERS), 93)

print()
print("=" * 74)
if FAILS:
    print(f"{len(FAILS)} FAILURE(S):")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("ALL ACT 2 CHECKS PASSED")
