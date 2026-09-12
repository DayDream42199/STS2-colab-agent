"""Batch 14: the combat-scoped counters."""
import random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Registry.card_registry import create_card, known_card_ids
from GameEngine.Effects.InstantEffects.instant_damage import InstantDamage
from GameEngine.Effects.InstantEffects.instant_hp_loss import InstantHpLoss

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

# --- Gold Axe: damage = cards played this combat ----------------------------
c, a, es = fight(seed=2)
play(c, a[0], "gold_axe", es[0])
# The tally is bumped after a card resolves, so a card never counts itself -
# the same rule that keeps Stack out of its own discard pile.
check("Gold Axe does not count itself", es[0].current_hp == 400,
      es[0].current_hp)

c, a, es = fight(seed=2)
for _ in range(4):
    play(c, a[0], "defend")
hp = es[0].current_hp
play(c, a[0], "gold_axe", es[0])
check("4 cards played before it -> 4 damage", es[0].current_hp == hp - 4,
      es[0].current_hp)

c, a, es = fight(seed=2)
for _ in range(3):
    play(c, a[0], "defend")
c.end_player_turn()
a[0].energy = 9
hp = es[0].current_hp
play(c, a[0], "gold_axe", es[0])
check("the count survives the turn boundary", es[0].current_hp == hp - 3,
      es[0].current_hp)

c, a, es = fight(n_allies=2, seed=2)
for _ in range(3):
    play(c, a[1], "defend")
hp = es[0].current_hp
play(c, a[0], "gold_axe", es[0])
check("Gold Axe counts only its own player's cards", es[0].current_hp == hp,
      es[0].current_hp)

# --- Tear Asunder: one extra hit per HP-loss event --------------------------
c, a, es = fight(seed=3)
play(c, a[0], "tear_asunder", es[0])
check("Tear Asunder with no HP lost hits once for 5", es[0].current_hp == 395,
      es[0].current_hp)

c, a, es = fight(seed=3)
a[0].block = 0
c._resolve(InstantDamage(source=es[0], target=a[0], amount=3))
play(c, a[0], "tear_asunder", es[0])
check("one HP-loss event -> two hits", es[0].current_hp == 390,
      es[0].current_hp)

c, a, es = fight(seed=3)
a[0].block = 0
for _ in range(3):
    c._resolve(InstantHpLoss(source=a[0], target=a[0], amount=1))
play(c, a[0], "tear_asunder", es[0])
check("three events -> four hits", es[0].current_hp == 380, es[0].current_hp)

c, a, es = fight(seed=3)
a[0].block = 0
c._resolve(InstantDamage(source=es[0], target=a[0], amount=20))
play(c, a[0], "tear_asunder", es[0])
check("it counts events, not HP: one big hit is still one",
      es[0].current_hp == 390, es[0].current_hp)

c, a, es = fight(seed=3)
a[0].block = 50
c._resolve(InstantDamage(source=es[0], target=a[0], amount=10))
play(c, a[0], "tear_asunder", es[0])
check("a fully blocked hit is not an HP-loss event",
      es[0].current_hp == 395, es[0].current_hp)

c, a, es = fight(seed=3)
a[0].block = 0
c._resolve(InstantHpLoss(source=a[0], target=a[0], amount=1))
c.end_player_turn()
a[0].energy = 9
a[0].block = 0
hp = es[0].current_hp
play(c, a[0], "tear_asunder", es[0])
check("the count survives the turn boundary", es[0].current_hp < hp - 5,
      es[0].current_hp)

# --- Gang Up: +5 per other player who attacked this enemy this turn ---------
c, a, es = fight(n_allies=3, seed=4)
play(c, a[0], "gang_up", es[0])
check("Gang Up alone deals 5", es[0].current_hp == 395, es[0].current_hp)

c, a, es = fight(n_allies=3, seed=4)
play(c, a[1], "strike", es[0])
hp = es[0].current_hp
play(c, a[0], "gang_up", es[0])
check("one other attacker -> 10", es[0].current_hp == hp - 10, es[0].current_hp)

c, a, es = fight(n_allies=3, seed=4)
play(c, a[1], "strike", es[0])
play(c, a[2], "strike", es[0])
hp = es[0].current_hp
play(c, a[0], "gang_up", es[0])
check("two other attackers -> 15", es[0].current_hp == hp - 15, es[0].current_hp)

c, a, es = fight(n_allies=3, seed=4)
for _ in range(3):
    play(c, a[1], "strike", es[0])
hp = es[0].current_hp
play(c, a[0], "gang_up", es[0])
check("the same attacker three times still counts once",
      es[0].current_hp == hp - 10, es[0].current_hp)

c, a, es = fight(n_allies=3, seed=4)
play(c, a[0], "strike", es[0])
hp = es[0].current_hp
play(c, a[0], "gang_up", es[0])
check("your own attacks do not count", es[0].current_hp == hp - 5,
      es[0].current_hp)

c, a, es = fight(n_allies=3, n_enemies=2, seed=4)
play(c, a[1], "strike", es[1])
hp = es[0].current_hp
play(c, a[0], "gang_up", es[0])
check("attacks on a different enemy do not count",
      es[0].current_hp == hp - 5, es[0].current_hp)

c, a, es = fight(n_allies=3, seed=4)
play(c, a[1], "strike", es[0])
c.end_player_turn()
a[0].energy = 9
hp = es[0].current_hp
play(c, a[0], "gang_up", es[0])
check("it is per turn, so the count resets", es[0].current_hp == hp - 5,
      es[0].current_hp)

print()
print("ALL BATCH 14 CHECKS PASSED" if not bad else "FAILURES: %d" % len(bad))
for b in bad:
    print("   ", b)

import sys as _sys
_sys.exit(1 if bad else 0)
