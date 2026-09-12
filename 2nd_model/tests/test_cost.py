"""Batch 13: cost modification and X-cost."""
import random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Registry.card_registry import create_card, known_card_ids

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
        a.energy = 3
    return c, allies, enemies

def play(c, ally, card_id, target=None):
    ally.hand = [card_id]
    return c.play_card(ally, 0, target=target)

check("registry has 223 cards", len(known_card_ids()) == 223, len(known_card_ids()))

# --- Stomp: 1 less per Attack played this turn ------------------------------
c, a, es = fight(n_enemies=2, seed=2)
check("Stomp starts at 3", c.card_cost(a[0], create_card("stomp")) == 3,
      c.card_cost(a[0], create_card("stomp")))
a[0].energy = 9
play(c, a[0], "strike", es[0])
check("one Attack played -> Stomp costs 2",
      c.card_cost(a[0], create_card("stomp")) == 2,
      c.card_cost(a[0], create_card("stomp")))
play(c, a[0], "defend")
check("a Skill does not make Stomp cheaper",
      c.card_cost(a[0], create_card("stomp")) == 2,
      c.card_cost(a[0], create_card("stomp")))
play(c, a[0], "strike", es[0])
play(c, a[0], "strike", es[0])
check("three Attacks -> Stomp is free",
      c.card_cost(a[0], create_card("stomp")) == 0,
      c.card_cost(a[0], create_card("stomp")))
play(c, a[0], "strike", es[0])
check("Stomp never goes below 0",
      c.card_cost(a[0], create_card("stomp")) == 0,
      c.card_cost(a[0], create_card("stomp")))

c, a, es = fight(n_enemies=2, seed=2)
a[0].energy = 9
for _ in range(3):
    play(c, a[0], "strike", es[0])
before = a[0].energy
hp = [e.current_hp for e in es]
play(c, a[0], "stomp")
check("Stomp at 0 spends nothing", a[0].energy == before, a[0].energy)
check("Stomp hits all enemies for 12",
      [e.current_hp for e in es] == [h - 12 for h in hp],
      [e.current_hp for e in es])
c.end_player_turn()
check("the discount resets next turn",
      c.card_cost(a[0], create_card("stomp")) == 3,
      c.card_cost(a[0], create_card("stomp")))

# --- Midnight: 1 less per card exhausted this combat, by anyone -------------
c, a, es = fight(seed=3)
check("Midnight starts at 12", c.card_cost(a[0], create_card("midnight")) == 12,
      c.card_cost(a[0], create_card("midnight")))
a[0].energy = 9
a[0].hand = ["cinder", "strike", "defend"]
c.play_card(a[0], 0, target=es[0])        # Cinder exhausts a card + itself
exhausted = c.combat_counters.get("cards_exhausted", 0)
check("exhausting cards is counted combat-wide", exhausted > 0, exhausted)
check("Midnight is cheaper by that many",
      c.card_cost(a[0], create_card("midnight")) == 12 - exhausted,
      c.card_cost(a[0], create_card("midnight")))
c.end_player_turn()
check("the discount survives the turn boundary",
      c.card_cost(a[0], create_card("midnight")) == 12 - exhausted,
      c.card_cost(a[0], create_card("midnight")))

c, a, es = fight(n_allies=2, seed=3)
a[1].energy = 9
a[1].hand = ["cinder", "strike", "defend"]
c.play_card(a[1], 0, target=es[0])
check("another player's exhausts count for Midnight too",
      c.card_cost(a[0], create_card("midnight")) < 12,
      c.card_cost(a[0], create_card("midnight")))

c, a, es = fight(seed=3)
c.combat_counters["cards_exhausted"] = 20
check("Midnight never goes below 0",
      c.card_cost(a[0], create_card("midnight")) == 0,
      c.card_cost(a[0], create_card("midnight")))

# --- Unrelenting: the next Attack costs 0 -----------------------------------
c, a, es = fight(seed=4)
a[0].energy = 3
play(c, a[0], "unrelenting", es[0])
check("Unrelenting deals 14", es[0].current_hp == 386, es[0].current_hp)
check("Unrelenting cost its own 2", a[0].energy == 1, a[0].energy)
check("it grants one free Attack", a[0].free_next_attack == 1)
play(c, a[0], "defend")
check("a Skill does not spend the grant", a[0].free_next_attack == 1)
check("and the Skill still cost its 1", a[0].energy == 0, a[0].energy)
play(c, a[0], "strike", es[0])
check("the next Attack is free", a[0].energy == 0, a[0].energy)
check("the grant is spent", a[0].free_next_attack == 0)

c, a, es = fight(seed=4)
a[0].energy = 2
play(c, a[0], "unrelenting", es[0])
c.end_player_turn()
check("the grant has no deadline - it survives the turn",
      a[0].free_next_attack == 1, a[0].free_next_attack)

# --- Corruption: Skills cost 0 and Exhaust ----------------------------------
c, a, es = fight(seed=5)
a[0].energy = 9
play(c, a[0], "corruption")
check("Corruption zeroes a Skill's cost",
      c.card_cost(a[0], create_card("defend")) == 0,
      c.card_cost(a[0], create_card("defend")))
check("Attacks still cost", c.card_cost(a[0], create_card("strike")) == 1,
      c.card_cost(a[0], create_card("strike")))
before = a[0].energy
play(c, a[0], "defend")
check("playing a Skill spends nothing", a[0].energy == before, a[0].energy)
check("the Skill is exhausted, not discarded",
      a[0].exhaust_pile == ["defend"] and "defend" not in a[0].discard_pile,
      (a[0].exhaust_pile, a[0].discard_pile))
play(c, a[0], "strike", es[0])
check("an Attack still goes to the discard", "strike" in a[0].discard_pile,
      a[0].discard_pile)
check("Corruption is permanent", a[0].get_status("corruption") is not None)
c.end_player_turn()
check("Corruption survives the turn", a[0].get_status("corruption") is not None)

# --- Enlightenment: everything costs at most 1 ------------------------------
c, a, es = fight(seed=6)
a[0].energy = 9
check("Bludgeon normally costs 2",
      c.card_cost(a[0], create_card("bludgeon")) == 2,
      c.card_cost(a[0], create_card("bludgeon")))
play(c, a[0], "enlightenment")
check("Enlightenment caps Bludgeon at 1",
      c.card_cost(a[0], create_card("bludgeon")) == 1,
      c.card_cost(a[0], create_card("bludgeon")))
check("it does not raise a card that already costs 0",
      c.card_cost(a[0], create_card("anger")) == 0,
      c.card_cost(a[0], create_card("anger")))
check("Enlightenment exhausts itself", a[0].exhaust_pile == ["enlightenment"],
      a[0].exhaust_pile)
c.end_player_turn()
check("the cap is gone next turn",
      c.card_cost(a[0], create_card("bludgeon")) == 2,
      c.card_cost(a[0], create_card("bludgeon")))
check("the status itself expired",
      a[0].get_status("enlightenment") is None, a[0].statuses)

c, a, es = fight(seed=6)
a[0].energy = 9
play(c, a[0], "corruption")
play(c, a[0], "enlightenment")
check("Corruption's 0 for Skills survives Enlightenment's cap",
      c.card_cost(a[0], create_card("defend")) == 0,
      c.card_cost(a[0], create_card("defend")))

# --- X-cost -----------------------------------------------------------------
c, a, es = fight(n_enemies=2, seed=7)
a[0].energy = 3
check("an X card costs everything you have",
      c.card_cost(a[0], create_card("whirlwind")) == 3,
      c.card_cost(a[0], create_card("whirlwind")))
hp = [e.current_hp for e in es]
play(c, a[0], "whirlwind")
check("Whirlwind hits all enemies X times for 5",
      [e.current_hp for e in es] == [h - 15 for h in hp],
      [e.current_hp for e in es])
check("Whirlwind drained the energy", a[0].energy == 0, a[0].energy)

c, a, es = fight(n_enemies=2, seed=7)
a[0].energy = 0
hp = [e.current_hp for e in es]
play(c, a[0], "whirlwind")
check("Whirlwind at 0 energy is a legal no-op",
      [e.current_hp for e in es] == hp, [e.current_hp for e in es])

c, a, es = fight(n_enemies=3, seed=8)
a[0].energy = 2
total_before = sum(e.current_hp for e in es)
play(c, a[0], "volley")
check("Volley fires X shots of 10",
      sum(e.current_hp for e in es) == total_before - 20,
      sum(e.current_hp for e in es))

c, a, es = fight(seed=9)
a[0].energy = 2
a[0].draw_pile = ["defend", "strike", "strike"]   # top two are strikes
hp = es[0].current_hp
play(c, a[0], "cascade")
check("Cascade plays the top X cards", es[0].current_hp == hp - 12,
      es[0].current_hp)
check("Cascade took them off the draw pile", a[0].draw_pile == ["defend"],
      a[0].draw_pile)

c, a, es = fight(seed=9)
a[0].energy = 5
a[0].draw_pile = ["strike"]
hp = es[0].current_hp
play(c, a[0], "cascade")
check("Cascade copes with a short draw pile", es[0].current_hp == hp - 6,
      es[0].current_hp)

# --- an auto-played X card has no energy behind it --------------------------
c, a, es = fight(n_enemies=2, seed=10)
a[0].energy = 9
a[0].draw_pile = ["whirlwind"]
hp = [e.current_hp for e in es]
play(c, a[0], "havoc")
check("Havoc playing Whirlwind deals nothing - nobody paid for it",
      [e.current_hp for e in es] == hp, [e.current_hp for e in es])
check("but it was still played and exhausted",
      a[0].exhaust_pile == ["whirlwind"], a[0].exhaust_pile)

# --- the free-play tally still wins over a dynamic cost ---------------------
c, a, es = fight(seed=11)
a[0].energy = 0
a[0].free_this_turn = ["midnight"]
a[0].hand = ["midnight"]
c.play_card(a[0], 0, target=es[0])
check("a free grant beats even a 12-cost card", es[0].current_hp == 340,
      es[0].current_hp)

print()
print("ALL BATCH 13 CHECKS PASSED" if not bad else "FAILURES: %d" % len(bad))
for b in bad:
    print("   ", b)

import sys as _sys
_sys.exit(1 if bad else 0)
