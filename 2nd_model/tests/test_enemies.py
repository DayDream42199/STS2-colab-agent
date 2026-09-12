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

# --- party cap: co-op is one to four players ---------------------------------
def party(n):
    return [create_ally("testally1", "p%d" % (i + 1), rng=random.Random(i)) for i in range(n)]

def refuses(build):
    try:
        build()
    except ValueError as error:
        return str(error)
    return None

c = Combat(party(4), [create_enemy("dummy1", "e1", rng=random.Random(1))], rng=random.Random(1))
c.start()
check("four players is a legal fight", len(c.allies) == 4 and c.enemies[0].max_hp > 0)
msg = refuses(lambda: Combat(party(5), [create_enemy("dummy1", "e1")]))
check("five players is refused before anything is built",
      msg is not None and "1 to 4 players" in msg, msg)
msg = refuses(lambda: Combat([], [create_enemy("dummy1", "e1")]))
check("no players is refused too", msg is not None, msg)

from session import Session
msg = refuses(lambda: Session(combat_factory=Combat, required_players=5))
check("Session refuses REQUIRED_PLAYERS above the cap at startup",
      msg is not None and "1 to 4" in msg, msg)
check("Session still accepts 4",
      Session(combat_factory=Combat, required_players=4).required_players == 4)

# --- Act 1 slimes and the Wriggler: enemies that hand out status cards ------
SLIMES = {"leafslimesmall": (11, 15), "leafslimemedium": (32, 35),
          "twigslimesmall": (7, 11), "twigslimemedium": (26, 28), "wriggler": (17, 21)}

for kind, (lo, hi) in SLIMES.items():
    rolled = {create_enemy(kind, "e1", rng=random.Random(s)).max_hp for s in range(60)}
    check("%s HP rolls inside %d-%d and reaches both ends" % (kind, lo, hi),
          min(rolled) == lo and max(rolled) == hi, sorted(rolled))

def small_fight(kind, players=2, seed=3, scale=False):
    allies = [create_ally("testally1", "p%d" % (i + 1), rng=random.Random(seed + i))
              for i in range(players)]
    foe = create_enemy(kind, "e1", rng=random.Random(seed))
    c = Combat(allies, [foe], rng=random.Random(seed), scale_enemies=scale)
    c.start()
    for a in allies:
        a.max_hp = a.current_hp = 200
        a.block = 0
    return c, allies, foe

def status_cards(p, card_id):
    return [r for r in p.hand + p.draw_pile + p.discard_pile if r == card_id]

def named(c, foe, allies):
    v = c.find_unit(foe.intent["target"])
    return v, [p for p in allies if p is not v][0]

check("Leaf Slime (S) is shown by its name, not its class",
      create_enemy("leafslimesmall", "e1").to_dict()["name"] == "Leaf Slime (S)")

# the rhythm: status shot first, then the hit, alternating - every one of them
for kind, opener, hit, dmg, count, card in (
        ("leafslimesmall", "Goop", "Tackle", 3, 1, "slimed"),
        ("leafslimemedium", "Sticky Shot", "Clump Shot", 8, 2, "slimed"),
        ("twigslimemedium", "Sticky Shot", "Chomp", 11, 1, "slimed"),
        ("wriggler", "Wriggle", "Nasty Bite", 6, 1, "infection")):
    c, a, foe = small_fight(kind)
    check("%s opens with %s, aimed at one named player" % (kind, opener),
          foe.intent["name"] == opener and foe.intent["type"] == "debuff"
          and foe.intent["target"] in ("p1", "p2"), foe.intent)
    v, o = named(c, foe, a)
    pass_turn(c, a)
    check("...%d %s lands in that player's discard pile" % (count, card),
          len(status_cards(v, card)) == count
          and len([r for r in v.discard_pile if r == card]) == count,
          [str(r) for r in v.discard_pile])
    check("...and the other player gets none", not status_cards(o, card))
    check("turn 2 is %s for %d" % (hit, dmg), foe.intent["name"] == hit
          and foe.intent["amount"] == dmg, foe.intent)
    v, o = named(c, foe, a)
    hp = v.current_hp
    pass_turn(c, a)
    bonus = foe.get_status("strength").amount if foe.get_status("strength") else 0
    check("...which hits the named player for %d" % (dmg + bonus),
          v.current_hp == hp - dmg - bonus, hp - v.current_hp)
    check("turn 3 is %s again" % opener, foe.intent["name"] == opener, foe.intent)

c, a, foe = small_fight("wriggler")
pass_turn(c, a)
check("Wriggle also gives the Wriggler 2 Strength", foe.get_status("strength").amount == 2)
pass_turn(c, a); pass_turn(c, a)
check("...stacking to 4 on the second Wriggle", foe.get_status("strength").amount == 4)

c, a, foe = small_fight("twigslimesmall")
hp = a[0].current_hp
check("Twig Slime (S) has one move, Tackle 4", foe.intent["name"] == "Tackle"
      and foe.intent["amount"] == 4)
for _ in range(3):
    pass_turn(c, a)
    check("...every turn", foe.intent["name"] == "Tackle")
check("three Tackles took 12 off the party in total",
      sum(200 - p.current_hp for p in a) == 12, [p.current_hp for p in a])

# the cards they hand out actually work
c, a, foe = small_fight("leafslimemedium", seed=5)
v, o = named(c, foe, a)
pass_turn(c, a)
v.hand = [r for r in v.discard_pile if r == "slimed"][:1]
v.discard_pile = [r for r in v.discard_pile if r not in v.hand]
v.draw_pile = [CardRef("strike")] * 3
v.energy = 3
c.play_card(v, 0)
check("a Slimed costs 1, draws 1 and exhausts", v.energy == 2 and len(v.hand) == 1
      and v.hand[0] == "strike" and v.exhaust_pile == ["slimed"],
      (v.energy, v.hand, v.exhaust_pile))

c, a, foe = small_fight("wriggler", seed=5)
v, o = named(c, foe, a)
pass_turn(c, a)
v.hand = status_cards(v, "infection")[:1]
v.discard_pile = [r for r in v.discard_pile if r != "infection"]
hp = v.current_hp
c.end_player_turn()
check("an Infection held at end of turn costs 3 HP, once, with two players in the fight "
      "(plus Nasty Bite 6 + 2 Strength = 8)", v.current_hp == hp - 3 - 8, hp - v.current_hp)

# the bug that check found: TURN_END is emitted once per ally, and every hand
# used to react to every emission, so a held Burn hit once per player
c, a, foe = small_fight("twigslimesmall", players=4, seed=6)
for p in a:
    p.hand = []
a[0].hand = [CardRef("burn")]
foe.get_effects = lambda context: []
hp = a[0].current_hp
c.end_player_turn()
check("a Burn held by one of four players deals 2, not 8", a[0].current_hp == hp - 2,
      hp - a[0].current_hp)

# --- the plain Act 1 pool: damage, Strength and Block cycles ------------------
# Each row of a script: (move announced, HP the player loses, enemy Block after
# the move, enemy Strength after). Solo and unscaled, so these are the wiki's
# numbers. Block is checked right after the move; it clears at the enemy's next.
SCRIPTS = {
    "nibbit": ((42, 46), [("Butt", 12, 0, 0), ("Hesitant Slice", 6, 5, 0),
                          ("Hiss", 0, 0, 2), ("Butt", 14, 0, 2),
                          ("Hesitant Slice", 8, 5, 2), ("Hiss", 0, 0, 4)]),
    "snappingjaxfruit": ((31, 33), [("Energy Orb", 3, 0, 2), ("Energy Orb", 5, 0, 4),
                                    ("Energy Orb", 7, 0, 6)]),
    "fuzzywurmcrawler": ((55, 57), [("Acid Goop", 4, 0, 0), ("Inhale", 0, 0, 7),
                                    ("Acid Goop", 11, 0, 7), ("Acid Goop", 11, 0, 7),
                                    ("Inhale", 0, 0, 14), ("Acid Goop", 18, 0, 14)]),
    "assassinraider": ((18, 23), [("Killshot", 10, 0, 0)] * 3),
    "axeraider": ((20, 22), [("Swing", 5, 5, 0), ("Big Swing", 12, 0, 0),
                             ("Swing", 5, 5, 0)]),
    "bruteraider": ((30, 33), [("Beat", 7, 0, 0), ("Clap", 0, 0, 3), ("Beat", 10, 0, 3),
                               ("Clap", 0, 0, 6)]),
    "crossbowraider": ((18, 21), [("Reload", 0, 3, 0), ("Fire!", 14, 0, 0),
                                  ("Reload", 0, 3, 0)]),
}

def play_out(kind, turns, players=1, seed=2, scale=False):
    c, a, foe = small_fight(kind, players=players, seed=seed, scale=scale)
    got = []
    for _ in range(turns):
        name = foe.intent["name"]
        victim = c.find_unit(foe.intent["target"]) or a[0]
        hp = victim.current_hp
        pass_turn(c, a)
        strength = foe.get_status("strength")
        got.append((name, hp - victim.current_hp, foe.block, strength.amount if strength else 0))
    return got

for kind, ((lo, hi), script) in SCRIPTS.items():
    rolled = {create_enemy(kind, "e1", rng=random.Random(s)).max_hp for s in range(60)}
    check("%s HP rolls %d-%d" % (kind, lo, hi), min(rolled) == lo and max(rolled) == hi,
          sorted(rolled))
    got = play_out(kind, len(script))
    check("%s plays its script: %s" % (kind, " / ".join(m for m, _, _, _ in script)),
          got == script, [g for g, s in zip(got, script) if g != s])

check("Snapping Jaxfruit is shown by its name",
      create_enemy("snappingjaxfruit", "e1").to_dict()["name"] == "Snapping Jaxfruit")
check("the Reload intent reads as block",
      create_enemy("crossbowraider", "e1").to_dict()["intent"] is None)  # not chosen yet
c, a, foe = small_fight("crossbowraider")
check("...once chosen: type block, no damage", foe.intent["type"] == "block"
      and foe.intent["amount"] == 0, foe.intent)

# --- the debuffers: one new status each --------------------------------------
# Same table shape; the fifth column is the statuses on the victim after the move.
DEBUFFERS = {
    "flyconid": ((47, 49), [("Weakening Spores", 0, {"vulnerable": 2}),
                            ("Frail Spores", 12, {"vulnerable": 1, "frail": 2}),   # 8 x 1.5
                            ("Smash", 11, {"frail": 1}),                            # vuln gone
                            ("Frail Spores", 8, {"frail": 2})]),                    # 0 + 2
    "slitheringstrangler": ((53, 55), [("Constrict", 0, {"constrict": 3}),
                                       ("Thwack", 7 + 3, {"constrict": 3}),        # + Constrict at turn end
                                       ("Lash", 12 + 3, {"constrict": 3}),
                                       ("Thwack", 7 + 3, {"constrict": 3})]),
    "vineshambler": ((61, 61), [("Swipe", 12, {}), ("Grasping Vines", 8, {"tangled": 1}),
                                ("Chomp", 16, {}), ("Swipe", 12, {})]),
    "shrinkerbeetle": ((38, 40), [("Shrinker", 0, {"shrink": 3}), ("Chomp", 7, {"shrink": 2}),
                                  ("Stomp", 13, {"shrink": 1}), ("Chomp", 7, {}),
                                  ("Stomp", 13, {})]),
    "mawler": ((72, 72), [("Roar", 0, {"vulnerable": 3}), ("Rip and Tear", 21, {"vulnerable": 2}),
                          ("Claw", 12, {"vulnerable": 1}),                          # 6 + 6
                          ("Rip and Tear", 14, {}), ("Claw", 8, {})]),              # Vulnerable gone
    "trackerraider": ((21, 25), [("Track", 0, {"frail": 2}), ("Unleash the Hounds", 8, {"frail": 1}),
                                 ("Track", 0, {"frail": 2}), ("Unleash the Hounds", 8, {"frail": 1})]),
    # Strength: Charge Up 2, then +2 after every Repeater Blast
    "cubexconstruct": ((65, 65), [("Charge Up", 0, {}), ("Repeater Blast", 7 + 2, {}),
                                  ("Expel Blast", (5 + 4) * 2, {}), ("Repeater Blast", 7 + 4, {}),
                                  ("Expel Blast", (5 + 6) * 2, {})]),
}

def play_statuses(kind, turns, seed=2):
    c, a, foe = small_fight(kind, players=1, seed=seed)
    got = []
    for _ in range(turns):
        name = foe.intent["name"]
        hp = a[0].current_hp
        pass_turn(c, a)
        got.append((name, hp - a[0].current_hp,
                    {k: v.amount for k, v in a[0].statuses.items()}))
    return got

for kind, ((lo, hi), script) in DEBUFFERS.items():
    rolled = {create_enemy(kind, "e1", rng=random.Random(s)).max_hp for s in range(60)}
    check("%s HP %d-%d" % (kind, lo, hi), min(rolled) == lo and max(rolled) == hi, sorted(rolled))
    got = play_statuses(kind, len(script))
    check("%s plays its script: %s" % (kind, " / ".join(m for m, _, _ in script)),
          got == script, [(g, s) for g, s in zip(got, script) if g != s])

# --- the three new statuses, in isolation -------------------------------------
from GameEngine.Registry.card_registry import create_card
from GameEngine.Effects.StatusEffects.shrink import Shrink
from GameEngine.Effects.StatusEffects.constrict import Constrict
from GameEngine.Effects.StatusEffects.tangled import Tangled
from GameEngine.Effects.StatusEffects.vulnerable import Vulnerable
from GameEngine.Effects.StatusEffects.weak import Weak

def solo_dummy(seed=1):
    c, a, foe = small_fight("shrinkerbeetle", players=1, seed=seed)
    foe.get_effects = lambda context: []             # a punching bag from here on
    a[0].energy = 9
    return c, a[0], foe

# Shrink: 30% off the player's attacks, stacks with Weak, dies with its applier
c, p, foe = solo_dummy()
p.apply_status(Shrink(source=foe, target=p, amount=3))
p.hand = [CardRef("strike")]; hp = foe.current_hp; c.play_card(p, 0, target=foe)
check("Shrink: a Strike deals 6 x 0.7 = 4", hp - foe.current_hp == 4, hp - foe.current_hp)
p.apply_status(Weak(source=foe, target=p, amount=2))
p.hand = [CardRef("strike")]; hp = foe.current_hp; c.play_card(p, 0, target=foe)
check("Shrink and Weak stack: 6 x 0.7 x 0.75 = 3", hp - foe.current_hp == 3, hp - foe.current_hp)
p.remove_status("weak")
other = create_enemy("twigslimesmall", "e2", rng=random.Random(1))
other.get_effects = lambda context: []               # joined late: no intent chosen yet
c.enemies.append(other)
foe.current_hp = 0                                    # the Beetle dies
p.hand = [CardRef("strike")]; hp = other.current_hp; c.play_card(p, 0, target=other)
check("...and Shrink stops working the moment the Beetle is dead: 6 again",
      hp - other.current_hp == 6, hp - other.current_hp)
c.end_player_turn()
check("...and is culled at the next tick", p.get_status("shrink") is None, p.statuses.keys())

# Constrict: end-of-turn damage, blockable, not an attack, only while the Strangler lives
c, p, foe = solo_dummy()
p.apply_status(Constrict(source=foe, target=p, amount=3))
p.apply_status(Vulnerable(source=foe, target=p, amount=5))
p.hand = []; hp = p.current_hp; c.end_player_turn()
check("Constrict: 3 at end of turn, and Vulnerable does not touch it (not an attack)",
      hp - p.current_hp == 3, hp - p.current_hp)
p.hand = [CardRef("defend")]; c.play_card(p, 0); hp = p.current_hp
p.hand = []; c.end_player_turn()
check("...Block stops it: Defend 5 soaks all 3", hp == p.current_hp, hp - p.current_hp)
check("...and it does not decay", p.get_status("constrict").amount == 3)
foe.current_hp = 0
p.hand = []; hp = p.current_hp; c.end_player_turn()
check("...the Strangler dead: no damage, status gone",
      hp == p.current_hp and p.get_status("constrict") is None,
      (hp - p.current_hp, list(p.statuses)))

# Tangled: Attacks cost 1 more; Skills do not; a free Attack stays free
c, p, foe = solo_dummy()
p.apply_status(Tangled(source=foe, target=p, amount=1))
strike, defend = create_card("strike"), create_card("defend")
check("Tangled: Strike costs 2, Defend still 1",
      (c.card_cost(p, strike), c.card_cost(p, defend)) == (2, 1),
      (c.card_cost(p, strike), c.card_cost(p, defend)))
p.free_next_attack = 1
p.hand = [CardRef("strike")]; p.energy = 3; c.play_card(p, 0, target=foe)
check("...an Attack made free (Unrelenting) is still free under Tangled", p.energy == 3, p.energy)
p.hand = []; c.end_player_turn()
check("...one turn later it is gone", p.get_status("tangled") is None, list(p.statuses))

# and the resolver rule the batch exposed: Vulnerable no longer inflates Burn
c, p, foe = solo_dummy()
p.apply_status(Vulnerable(source=foe, target=p, amount=3))
p.hand = [CardRef("burn")]; hp = p.current_hp; c.end_player_turn()
check("a Burn held by a Vulnerable player deals 2, not 3", hp - p.current_hp == 2, hp - p.current_hp)

# an enemy's Block from an attack rider is scaled for two players like any other
got = play_out("axeraider", 1, players=2, scale=True)
check("Axe Raider's Swing blocks 10 with two players (5 x 2)", got[0][2] == 10, got[0])
got = play_out("crossbowraider", 1, players=2, scale=True)
check("Crossbow Raider's Reload blocks 6 with two players (3 x 2)", got[0][2] == 6, got[0])

# co-op scaling applies to a rolled HP too
solo = create_enemy("leafslimemedium", "e1", rng=random.Random(9)).max_hp
c, a, foe = small_fight("leafslimemedium", seed=9, scale=True)
check("a ranged-HP enemy is scaled for two players: %d x 2 x 1.1 = %d" % (solo, round(solo * 2.2)),
      foe.max_hp == round(solo * 2.2), foe.max_hp)

print()
print("%d checks failed" % len(bad))
for label in bad:
    print("   ", label)

import sys as _sys
_sys.exit(1 if bad else 0)
