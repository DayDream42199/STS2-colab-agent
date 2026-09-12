"""Scripted enemies: the Move model, co-op scaling, targeting, The Insatiable."""
import json, random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Cards._card_ref import CardRef
from GameEngine.Effects.StatusEffects.strength import Strength

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))

def boss_fight(players=2, seed=1, act="act2", scale=True, ally_hp=300):
    allies = [create_ally("testally1", "p%d" % (i + 1), rng=random.Random(seed + i))
              for i in range(players)]
    boss = create_enemy("theinsatiable", "e1", rng=random.Random(seed))
    c = Combat(allies, [boss], rng=random.Random(seed), act=act, scale_enemies=scale)
    c.start()
    for a in allies:
        a.max_hp = a.current_hp = ally_hp
        a.energy = 9
    return c, allies, boss

def pass_turn(c, allies):
    for a in allies:
        a.hand = []
    c.end_player_turn()


# --- scaling ----------------------------------------------------------------
c, a, boss = boss_fight(players=1, scale=True)
check("alone, the boss has its printed 321 HP", boss.max_hp == 321, boss.max_hp)

c, a, boss = boss_fight(players=2, act="act2")
check("two players in act 2: 321 x 2 x 1.2 = 770", boss.max_hp == 770, boss.max_hp)

c, a, boss = boss_fight(players=2, act="act1")
check("act 1 factor is 1.1: 706", boss.max_hp == 706, boss.max_hp)

c, a, boss = boss_fight(players=3, act="act3boss")
check("three players, act 3 boss: 321 x 3 x 1.3 = 1252", boss.max_hp == 1252, boss.max_hp)

c, a, boss = boss_fight(players=2, scale=False)
check("scaling can be switched off", boss.max_hp == 321, boss.max_hp)

dummy = create_enemy("dummy1", "e1", rng=random.Random(1))
base = dummy.max_hp
Combat([create_ally("testally1", "p1", rng=random.Random(1)),
        create_ally("testally1", "p2", rng=random.Random(1))],
       [dummy], rng=random.Random(1), act="act1").start()
check("the old test dummy scales too", dummy.max_hp == round(base * 2.2), (base, dummy.max_hp))

# --- the script -------------------------------------------------------------
c, a, boss = boss_fight()
check("turn 1 intent is Liquify Ground, a debuff aimed at nobody in particular",
      boss.intent["name"] == "Liquify Ground" and boss.intent["type"] == "debuff"
      and boss.intent["target"] is None, boss.intent)
check("the intent is JSON-safe for the wire", json.dumps(boss.to_dict()) is not None)

pass_turn(c, a)
for p in a:
    check("%s has 4 Sandpit after Liquify" % p.unit_id,
          p.get_status("sandpit") is not None and p.get_status("sandpit").amount == 3,
          # 4 applied, then their own turn started and it ticked once
          p.get_status("sandpit").amount if p.get_status("sandpit") else None)
    escapes_draw = [r for r in p.draw_pile if r == "frantic_escape"]
    escapes_disc = [r for r in p.discard_pile if r == "frantic_escape"]
    check("%s: 3 Frantic Escape in the draw pile, 3 in the discard" % p.unit_id,
          len(escapes_draw) == 3 and len(escapes_disc) == 3,
          (len(escapes_draw), len(escapes_disc)))
    check("%s: the draw-pile ones are at the BOTTOM, not on top" % p.unit_id,
          p.draw_pile[:3] == ["frantic_escape"] * 3
          and "frantic_escape" not in p.hand,
          (p.draw_pile[:3], p.hand))

# The countdown is lethal on turn 5 and has its own section below; take it
# off here so the move cycle can be watched past that.
for p in a:
    p.remove_status("sandpit")

check("turn 2 intent: Thrash, 8 x 2, at a named player",
      boss.intent["name"] == "Thrash" and boss.intent["amount"] == 8
      and boss.intent["hits"] == 2 and boss.intent["target"] in ("p1", "p2"),
      boss.intent)
victim = c.find_unit(boss.intent["target"])
other = [p for p in a if p is not victim][0]
hp_v, hp_o = victim.current_hp, other.current_hp
pass_turn(c, a)
check("Thrash hits the named player twice for 8, and nobody else",
      victim.current_hp == hp_v - 16 and other.current_hp == hp_o,
      (hp_v - victim.current_hp, hp_o - other.current_hp))

check("turn 3 intent: Lunging Bite for 28", boss.intent["name"] == "Lunging Bite"
      and boss.intent["amount"] == 28, boss.intent)
victim = c.find_unit(boss.intent["target"])
hp_v = victim.current_hp
pass_turn(c, a)
check("Lunging Bite lands for 28", victim.current_hp == hp_v - 28, hp_v - victim.current_hp)

check("turn 4 intent: Salivate, a buff", boss.intent["name"] == "Salivate"
      and boss.intent["type"] == "buff", boss.intent)
pass_turn(c, a)
check("Salivate gives the boss 2 Strength", boss.get_status("strength") is not None
      and boss.get_status("strength").amount == 2, boss.statuses.keys())

check("turn 5: Thrash again - the cycle is Thrash, Lunge, Salivate, Thrash",
      boss.intent["name"] == "Thrash", boss.intent)
victim = c.find_unit(boss.intent["target"])
hp_v = victim.current_hp
pass_turn(c, a)
check("and its Strength now adds: 10 x 2", victim.current_hp == hp_v - 20,
      hp_v - victim.current_hp)
check("turn 6 wraps back to Thrash, never to Liquify",
      boss.intent["name"] == "Thrash", boss.intent)

# --- targeting --------------------------------------------------------------
c, a, boss = boss_fight(seed=3)
pass_turn(c, a)                                   # Liquify
for p in a:
    p.remove_status("sandpit")
picks = set()
for _ in range(12):
    if boss.intent["type"] == "attack":            # Salivate names nobody
        picks.add(boss.intent["target"])
    pass_turn(c, a)
check("over many turns the boss spreads its attacks across both players",
      picks == {"p1", "p2"}, picks)

c, a, boss = boss_fight(seed=5)
pass_turn(c, a)
target = c.find_unit(boss.intent["target"])
other = [p for p in a if p is not target][0]
target.current_hp = 0                             # dies before the boss acts
hp_o = other.current_hp
pass_turn(c, a)
check("if the named target dies first, the attack falls on a living ally instead",
      other.current_hp < hp_o, (hp_o, other.current_hp))

c, a, boss = boss_fight(seed=7)
pass_turn(c, a)
from GameEngine.Effects.StatusEffects.intercepting import Intercepting
target = c.find_unit(boss.intent["target"])
other = [p for p in a if p is not target][0]
other.apply_status(Intercepting(source=other, target=other, amount=1))
hp_t, hp_o = target.current_hp, other.current_hp
pass_turn(c, a)
check("Intercept still redirects a scripted enemy's named attack",
      target.current_hp == hp_t and other.current_hp < hp_o,
      (hp_t - target.current_hp, hp_o - other.current_hp))

# --- the whole Sandpit arc against the real boss ----------------------------
c, a, boss = boss_fight(seed=11, ally_hp=1000)
pass_turn(c, a)                                   # Liquify: 4 -> ticks to 3
for expected in (2, 1):
    pass_turn(c, a)
    check("Sandpit counts down to %d" % expected,
          all(p.get_status("sandpit").amount == expected for p in a),
          [p.get_status("sandpit").amount for p in a])
pass_turn(c, a)
check("...and both players are eaten: DEFEAT with 1000 HP each",
      c.is_over() and c.result.name == "DEFEAT" and all(not p.is_alive() for p in a),
      (c.result, [p.current_hp for p in a]))

c, a, boss = boss_fight(seed=11, ally_hp=1000)
pass_turn(c, a)                                   # sandpit 3
p1 = a[0]
# dig for the escapes: drop the rest of the deck so the bottom three surface,
# and keep the discard's three out of the reshuffle so exactly three arrive
p1.draw_pile = [r for r in p1.draw_pile if r == "frantic_escape"]
p1.discard_pile = [r for r in p1.discard_pile if r != "frantic_escape"]
p1.hand = []
c.end_player_turn()                               # sandpit 2; draws the 3 escapes
escapes = [r for r in p1.hand if r == "frantic_escape"]
check("with the deck dug through, the three escapes come to hand", len(escapes) == 3,
      p1.hand)
p1.energy = 9
for _ in range(3):
    c.play_card(p1, p1.hand.index("frantic_escape"))
check("three escapes push p1's Sandpit from 2 to 5", p1.get_status("sandpit").amount == 5,
      p1.get_status("sandpit").amount)
check("p2, who found none, is still at 2", a[1].get_status("sandpit").amount == 2,
      a[1].get_status("sandpit").amount)

# --- Aeonglass --------------------------------------------------------------
def glass_fight(players=2, seed=1, act="act1", scale=True, ally_hp=500):
    allies = [create_ally("testally1", "p%d" % (i + 1), rng=random.Random(seed + i))
              for i in range(players)]
    boss = create_enemy("aeonglass", "e1", rng=random.Random(seed))
    c = Combat(allies, [boss], rng=random.Random(seed), act=act, scale_enemies=scale)
    c.start()
    for a in allies:
        a.max_hp = a.current_hp = ally_hp
        a.energy = 9
    return c, allies, boss

def victim_of(c, boss, allies):
    v = c.find_unit(boss.intent["target"])
    return v, [p for p in allies if p is not v][0]

c, a, boss = glass_fight(players=1)
check("Aeonglass alone: 512 HP", boss.max_hp == 512, boss.max_hp)
c, a, boss = glass_fight(players=2, act="act1")
check("two players, act 1: 512 x 2 x 1.1 = 1126", boss.max_hp == 1126, boss.max_hp)

# --- the cycle, and Block scaling -------------------------------------------
c, a, boss = glass_fight(players=1)
check("turn 1: Ebb, 22, at the only player",
      boss.intent["name"] == "Ebb" and boss.intent["amount"] == 22
      and boss.intent["target"] == "p1", boss.intent)
hp = a[0].current_hp
pass_turn(c, a)
check("Ebb hits for 22 and Aeonglass blocks 33 - unscaled, one player",
      a[0].current_hp == hp - 22 and boss.block == 33, (hp - a[0].current_hp, boss.block))

c, a, boss = glass_fight(players=2)
v, o = victim_of(c, boss, a)
hp = v.current_hp
pass_turn(c, a)
check("with two players Ebb's 33 Block is doubled to 66; the 22 is not",
      boss.block == 66 and v.current_hp == hp - 22, (boss.block, hp - v.current_hp))
a[0].hand = [CardRef("defend")]
c.play_card(a[0], 0)
check("...and a player's own Block is never scaled", a[0].block == 5, a[0].block)

check("turn 2: Eye Lasers, 11 x 2", boss.intent["name"] == "Eye Lasers"
      and boss.intent["amount"] == 11 and boss.intent["hits"] == 2, boss.intent)
v, o = victim_of(c, boss, a)
a[0].block = 0                                    # the Defend above
hp = v.current_hp
pass_turn(c, a)
check("Eye Lasers land for 22 on one player", v.current_hp == hp - 22, hp - v.current_hp)
check("and the Ebb Block was cleared at the start of its turn", boss.block == 0, boss.block)

check("turn 3: Increasing Intensity - a debuff that still names a player",
      boss.intent["name"] == "Increasing Intensity" and boss.intent["type"] == "debuff"
      and boss.intent["target"] in ("p1", "p2"), boss.intent)
v, o = victim_of(c, boss, a)
pass_turn(c, a)
# it lands in the discard, but the next turn's draw may have reshuffled it
# into the draw pile or hand already - so look everywhere it could be
def withers_of(p):
    return [r for r in p.hand + p.draw_pile + p.discard_pile if r == "wither"]
withers = withers_of(v)
check("the named player gets a Wither (bonus 0 the first time)",
      len(withers) == 1 and withers[0].bonus_damage == 0,
      [(str(r), r.bonus_damage) for r in withers])
check("and the other player gets nothing", not withers_of(o), withers_of(o))
check("Aeonglass gains 2 Strength", boss.get_status("strength").amount == 2,
      boss.get_status("strength").amount)

check("turn 4 wraps to Ebb", boss.intent["name"] == "Ebb", boss.intent)
v, o = victim_of(c, boss, a)
hp = v.current_hp
pass_turn(c, a)
check("...which now hits for 22 + 2 Strength", v.current_hp == hp - 24, hp - v.current_hp)

# --- escalation: each Intensity is worse ------------------------------------
c, a, boss = glass_fight(players=2, seed=4)
got = []
for turn in range(9):                                    # three full cycles
    if boss.intent["name"] == "Increasing Intensity":
        v = c.find_unit(boss.intent["target"])
        before = {id(r) for r in withers_of(v)}
        pass_turn(c, a)
        new = [r for r in withers_of(v) if id(r) not in before]
        got.append((new[0].bonus_damage if new else None, boss.get_status("strength").amount))
    else:
        pass_turn(c, a)
check("three Intensities hand out Wither, Wither+1, Wither+2 and stack 2, 3, 4 Strength",
      got == [(0, 2), (1, 5), (2, 9)], got)

# --- the Wither actually bites ----------------------------------------------
c, a, boss = glass_fight(players=1, seed=2)
a[0].hand = [CardRef("wither", bonus_damage=2)]
a[0].block = 0
hp = a[0].current_hp
boss.choose_intent = lambda context=None: setattr(boss, "intent", {"type": "buff", "name": "-", "amount": 0, "hits": 1, "target": None})
boss.get_effects = lambda context: []
c.end_player_turn()
check("a Wither+2 held at end of turn deals 5, and is not the boss's attack",
      a[0].current_hp == hp - 5, hp - a[0].current_hp)

print()
print("%d checks failed" % len(bad))
for label in bad:
    print("   ", label)

import sys as _sys
_sys.exit(1 if bad else 0)
