"""The scripted teammates (Plugins/teammates.py), and the Characteristic
Analyzer read against them: five bots of known style, every pairing, two
seats a fight, one deck, Act 1 enemies, through the real session with the
aura plugin. The analyzer should see each style on its own trait."""
import random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from GameEngine.Combat.combat import Combat
from GameEngine.Cards._card_ref import CardRef
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from Plugins import teammates as bots

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))


# --- what each bot picks ------------------------------------------------------------
print("== what each bot picks ==")
def table(hand, energy=3):
    allies = [create_ally("teammateironclad", "p%d" % (i + 1), rng=random.Random(1)) for i in range(2)]
    foes = [create_enemy("dummy1", "e1", rng=random.Random(1)), create_enemy("dummy1", "e2", rng=random.Random(1))]
    c = Combat(allies, foes, rng=random.Random(1), scale_enemies=False)
    c.start()
    foes[1].current_hp = 3                      # the weaker enemy
    allies[1].current_hp = 20                   # a hurt teammate
    allies[0].hand, allies[0].energy = [CardRef(i) for i in hand], energy
    return c, allies[0]

def first(style, hand, energy=3):
    c, p = table(hand, energy)
    action = bots.choose(style, c, p, random.Random(1))
    return (hand[action["hand_index"]], action["target_id"]) if action["type"] == "play_card" else action["type"]

HAND = ["defend", "inflame", "strike", "coordinate", "shrug_it_off"]
check("aggressive: the attack, at the weaker enemy", first("aggressive", HAND) == ("strike", "e2"),
      first("aggressive", HAND))
check("defensive: the most Block", first("defensive", HAND) == ("shrug_it_off", None), first("defensive", HAND))
check("scaling: the Power", first("scaling", HAND) == ("inflame", None), first("scaling", HAND))
check("team: the card for a teammate", first("team", HAND) == ("coordinate", "p2"), first("team", HAND))
check("nothing affordable: end turn", first("aggressive", HAND, energy=0) == "end_turn",
      first("aggressive", HAND, energy=0))
c, p = table(["strike", "defend"], energy=2)
for _ in range(3):
    action = bots.choose("aggressive", c, p, random.Random(1))
    if action["type"] != "play_card":
        break
    c.play_card(p, action["hand_index"], target=c.find_unit(action["target_id"]) if action["target_id"] else None)
check("the rest, once its own cards are played: Strike, then Defend, then end turn",
      not p.hand and p.energy == 0 and action == bots.END, (p.hand, p.energy, action))


# --- the analyzer, against them ---------------------------------------------------------
print("\n== the analyzer against them: every pairing, 4 fights each ==")
seats = bots.run(4)
found = bots.summary(seats)
for style, row in found.items():
    p = row["over_all"]
    print("   %-10s %3d turns  A %+.2f  S %+.2f  T %+.2f" % (style, row["turns"], p["A"], p["S"], p["T"]))
check("100 fights, every bot action accepted", len(seats) == 200 and sum(s["refused"] for s in seats) == 0,
      sum(s["refused"] for s in seats))
check("every style scored on plenty of turns", all(row["turns"] > 50 for row in found.values()),
      {s: r["turns"] for s, r in found.items()})

over = {style: row["over_all"] for style, row in found.items()}
for style, (trait, way) in bots.OWN_TRAIT.items():
    others = [over[o][trait] for o in bots.STYLES if o != style]
    leans = way * over[style][trait] > 0
    stands_out = all(way * over[style][trait] > way * v for v in others)
    check("over all its turns, %s leans %s%s and is the %s of the five"
          % (style, trait, "+" if way > 0 else "-", "highest" if way > 0 else "lowest"),
          leans and stands_out, {o: round(over[o][trait], 2) for o in bots.STYLES})

# Within one fight the aggressive and the team bot are the hardest pair to
# part: damage is in the team group, so the team bot's attacks read as
# Aggression and the aggressive bot's as Teamwork. 75%, not more, for that.
for style, row in bots.fight_by_fight(seats).items():
    trait, way = bots.OWN_TRAIT[style]
    check("fight by fight, %s comes out past its partner on %s in at least 75%% of mixed fights" % (style, trait),
          row["beat"] >= 0.75 * row["mixed"], row)
    check("and leans its way in at least 90%% of its seats with %s evidence" % trait,
          row["leaned"] >= 0.9 * row["with_evidence"], row)

once = bots.summary(bots.run(1))
check("the same seeds give the same profiles", bots.summary(bots.run(1)) == once)

print()
print("%d checks failed" % len(bad))
for label in bad:
    print("   ", label)

import sys as _sys
_sys.exit(1 if bad else 0)
