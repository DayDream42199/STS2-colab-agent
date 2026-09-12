"""Batch 15: reactive effects."""
import random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Registry.card_registry import create_card, known_card_ids
from GameEngine.Effects.StatusEffects.strength import Strength
from GameEngine.Effects.StatusEffects.vulnerable import Vulnerable

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))

def fight(n_allies=1, n_enemies=1, seed=1, enemy_hp=400):
    allies = [create_ally("testally1", "p%d" % (i+1), rng=random.Random(seed))
              for i in range(n_allies)]
    enemies = [create_enemy("dummy1", "e%d" % (i+1), rng=random.Random(seed))
               for i in range(n_enemies)]
    c = Combat(allies, enemies, rng=random.Random(seed)); c.start()
    for e in enemies:
        e.current_hp = e.max_hp = enemy_hp
    for a in allies:
        a.energy = 9
    return c, allies, enemies

def play(c, ally, card_id, target=None):
    ally.hand = [card_id]
    return c.play_card(ally, 0, target=target)

check("registry has 223 cards", len(known_card_ids()) == 223, len(known_card_ids()))

# --- Fisticuffs -------------------------------------------------------------
c, a, es = fight(seed=2)
play(c, a[0], "fisticuffs", es[0])
check("Fisticuffs deals 7", es[0].current_hp == 393, es[0].current_hp)
check("Fisticuffs blocks for the 7 it dealt", a[0].block == 7, a[0].block)

c, a, es = fight(seed=2)
a[0].apply_status(Strength(source=a[0], target=a[0], amount=4))
play(c, a[0], "fisticuffs", es[0])
check("the block follows the modified damage, not the printed value",
      a[0].block == 11 and es[0].current_hp == 389,
      (a[0].block, es[0].current_hp))

c, a, es = fight(seed=2)
es[0].block = 100
play(c, a[0], "fisticuffs", es[0])
check("damage soaked by enemy Block still counts as dealt",
      a[0].block == 7 and es[0].current_hp == 400,
      (a[0].block, es[0].current_hp))

c, a, es = fight(seed=2)
es[0].apply_status(Vulnerable(source=a[0], target=es[0], amount=1))
play(c, a[0], "fisticuffs", es[0])
check("Vulnerable raises both the damage and the block",
      a[0].block == 10 and es[0].current_hp == 390,
      (a[0].block, es[0].current_hp))

# --- Omnislice --------------------------------------------------------------
c, a, es = fight(n_enemies=3, seed=3)
play(c, a[0], "omnislice", es[1])
check("Omnislice hits the target for 8", es[1].current_hp == 392,
      es[1].current_hp)
check("and every other enemy for the same",
      [es[0].current_hp, es[2].current_hp] == [392, 392],
      [e.current_hp for e in es])

c, a, es = fight(n_enemies=3, seed=3)
a[0].apply_status(Strength(source=a[0], target=a[0], amount=5))
play(c, a[0], "omnislice", es[0])
check("the splash matches the modified hit, and Strength is not applied twice",
      [e.current_hp for e in es] == [387, 387, 387], [e.current_hp for e in es])

c, a, es = fight(n_enemies=3, seed=3)
es[2].current_hp = 0
play(c, a[0], "omnislice", es[0])
check("a dead enemy is not splashed", es[2].current_hp == 0, es[2].current_hp)

c, a, es = fight(seed=3)
play(c, a[0], "omnislice", es[0])
check("Omnislice with a single enemy just hits it once",
      es[0].current_hp == 392, es[0].current_hp)

# --- Feed -------------------------------------------------------------------
c, a, es = fight(seed=4)
max_before = a[0].max_hp
play(c, a[0], "feed", es[0])
check("Feed deals 10", es[0].current_hp == 390, es[0].current_hp)
check("a non-fatal Feed gives no Max HP", a[0].max_hp == max_before,
      a[0].max_hp)
check("Feed exhausts itself", a[0].exhaust_pile == ["feed"], a[0].exhaust_pile)

c, a, es = fight(n_enemies=2, seed=4)
es[0].current_hp = 4
max_before, hp_before = a[0].max_hp, a[0].current_hp
play(c, a[0], "feed", es[0])
check("a fatal Feed raises Max HP by 3", a[0].max_hp == max_before + 3,
      a[0].max_hp)
check("and current HP with it", a[0].current_hp == hp_before + 3,
      a[0].current_hp)
check("the enemy is dead", not es[0].is_alive(), es[0].current_hp)

c, a, es = fight(n_enemies=2, seed=4)
es[0].current_hp = 4
es[0].block = 50
max_before = a[0].max_hp
play(c, a[0], "feed", es[0])
check("a blocked Feed is not fatal, so no Max HP",
      a[0].max_hp == max_before and es[0].is_alive(),
      (a[0].max_hp, es[0].current_hp))

c, a, es = fight(n_enemies=2, seed=4)
es[0].current_hp = 4
a[0].max_hp = a[0].current_hp = 20
play(c, a[0], "feed", es[0])
check("Feed heals as it grows, so it never leaves a gap",
      a[0].current_hp == a[0].max_hp == 23,
      (a[0].current_hp, a[0].max_hp))

# --- the follow-up cannot chain ---------------------------------------------
c, a, es = fight(n_enemies=2, seed=5)
r = play(c, a[0], "omnislice", es[0])
check("the follow-up damage is reported on the wire too", len(r) == 2, len(r))
check("but it does not itself produce another follow-up",
      [e.current_hp for e in es] == [392, 392], [e.current_hp for e in es])

# --- a heal is not a status -------------------------------------------------
c, a, es = fight(seed=6)
seen = []
real_emit = c._emit
def spy(event, subject=None, **payload):
    seen.append(event.name)
    return real_emit(event, subject, **payload)
c._emit = spy
es[0].current_hp = 4
play(c, a[0], "feed", es[0])
check("gaining Max HP does not announce itself as a status",
      "STATUS_APPLIED" not in seen, seen)

print()
print("ALL BATCH 15 CHECKS PASSED" if not bad else "FAILURES: %d" % len(bad))
for b in bad:
    print("   ", b)

import sys as _sys
_sys.exit(1 if bad else 0)
