"""Every enemy, as the installed game's code has it (v0.107.1).

The rules that cover all of them: every enemy move lands on every living
player (the game hands each move combatState.PlayerCreatures), enemy HP and
Block scale for co-op, and an attack intent carries the damage it will do to
each player. Then each enemy's own numbers and move pattern.
"""
import json, random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Cards._card_ref import CardRef
from GameEngine.Effects.StatusEffects.strength import Strength
from GameEngine.Effects.StatusEffects.weak import Weak
from GameEngine.Effects.StatusEffects.vulnerable import Vulnerable
from GameEngine.Effects.StatusEffects.intercepting import Intercepting

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))

DECK = ["strike"] * 5 + ["defend"] * 4 + ["bash"]


def fight(kinds, players=1, seed=1, act="act1", scale=False, ally_hp=500):
    """A fight against `kinds` (one type id or several). The deck is pinned
    here so a test deck in TestAlly1 cannot change what these check."""
    kinds = [kinds] if isinstance(kinds, str) else list(kinds)
    allies = [create_ally("testally1", "p%d" % (i + 1), rng=random.Random(seed + i))
              for i in range(players)]
    for a in allies:
        a.deck = list(DECK)
    foes = [create_enemy(k, "e%d" % (i + 1), rng=random.Random(seed + 10 + i))
            for i, k in enumerate(kinds)]
    c = Combat(allies, foes, rng=random.Random(seed), act=act, scale_enemies=scale)
    c.start()
    for a in allies:
        a.max_hp = a.current_hp = ally_hp
        a.block = 0
    return c, allies, foes


def pass_turn(c, allies, keep=()):
    """End the turn with empty hands, so only the enemies act. Sandpit is
    taken off unless asked for, or The Insatiable eats everyone on turn 5."""
    for a in allies:
        a.hand = []
        if "sandpit" not in keep:
            a.remove_status("sandpit")
    c.end_player_turn()


def charges(unit, effect_id):
    status = unit.get_status(effect_id)
    return status.amount if status is not None else 0


def play_out(kind, turns, players=1, seed=2, scale=False):
    """Per enemy turn: (move, HP each player lost, enemy Block after, enemy
    Strength after)."""
    c, a, (foe,) = fight(kind, players, seed, scale=scale)
    rows = []
    for _ in range(turns):
        name = foe.intent["name"]
        hp = [p.current_hp for p in a]
        pass_turn(c, a)
        rows.append((name, [h - p.current_hp for h, p in zip(hp, a)], foe.block,
                     charges(foe, "strength")))
    return rows


def moves(kind, turns, seed, others=()):
    """The move names an enemy uses over `turns` turns."""
    c, a, foes = fight([kind] + list(others), 1, seed, ally_hp=5000)
    foe = foes[0]
    out = []
    for _ in range(turns):
        out.append(foe.intent["name"])
        pass_turn(c, a)
    return out


# ============================================================================
# every move lands on every player
# ============================================================================
c, a, (foe,) = fight("nibbit", players=3)
check("an enemy's intent names no target - it goes for everyone",
      "target" not in foe.intent, foe.intent)
hp = [p.current_hp for p in a]
pass_turn(c, a)                                           # Butt, 12
check("Nibbit's Butt hits all three players for 12",
      [h - p.current_hp for h, p in zip(hp, a)] == [12, 12, 12],
      [h - p.current_hp for h, p in zip(hp, a)])

c, a, (foe,) = fight("leafslimemedium", players=3)
pass_turn(c, a)                                           # Sticky Shot: 2 Slimed each
check("a status card goes to every player: 2 Slimed each",
      all(p.discard_pile.count("slimed") == 2 for p in a),
      [p.discard_pile.count("slimed") for p in a])

c, a, (foe,) = fight("mawler", players=2, seed=3)
c.enemies[0].history = [c.enemies[0]._claw]               # past the opener
foe.move = foe._branches[1].move                           # force Roar
foe.intent = dict(foe.intent, type="debuff", name="Roar")
pass_turn(c, a)
check("a debuff goes to every player: Roar's 3 Vulnerable on both",
      [charges(p, "vulnerable") for p in a] == [3, 3], [charges(p, "vulnerable") for p in a])

c, a, (foe,) = fight("nibbit", players=3)
a[1].current_hp = 0
hp = [p.current_hp for p in a]
pass_turn(c, a)
check("a dead player is not hit, the living ones are",
      [h - p.current_hp for h, p in zip(hp, a)] == [12, 0, 12],
      [h - p.current_hp for h, p in zip(hp, a)])

c, a, (foe,) = fight("nibbit", players=3)
a[0].apply_status(Intercepting(source=a[0], target=a[0], amount=1, covered=a[1]))
hp = [p.current_hp for p in a]
pass_turn(c, a)
check("Intercept takes the covered player's hit: p1 takes 12 x 2, p2 none, p3 its own",
      [h - p.current_hp for h, p in zip(hp, a)] == [24, 0, 12],
      [h - p.current_hp for h, p in zip(hp, a)])

# ============================================================================
# the intent shows the real damage, per player
# ============================================================================
c, a, (foe,) = fight("nibbit", players=2)
shown = lambda: c.to_dict()["enemies"][0]["intent"]["damage"]
check("an attack intent carries each player's damage", shown() == {"p1": 12, "p2": 12}, shown())
foe.apply_status(Strength(source=foe, target=foe, amount=2))
a[1].apply_status(Vulnerable(source=foe, target=a[1], amount=1))
check("with the enemy's 2 Strength, and p2 Vulnerable: 14 and 21",
      shown() == {"p1": 14, "p2": 21}, shown())
foe.apply_status(Weak(source=a[0], target=foe, amount=1))
check("Weaken the enemy mid-turn and the intent drops at once: 10 and 15",
      shown() == {"p1": 10, "p2": 15}, shown())
check("...and the enemy's own intent is left alone", "damage" not in foe.intent)
hp = [p.current_hp for p in a]
pass_turn(c, a)
check("the shown numbers are what landed", [h - p.current_hp for h, p in zip(hp, a)] == [10, 15],
      [h - p.current_hp for h, p in zip(hp, a)])
check("the state is still JSON", json.dumps(c.to_dict()) is not None)

# ============================================================================
# co-op scaling (HP and Block; damage never)
# ============================================================================
c, a, (boss,) = fight("theinsatiable", players=1, scale=True)
check("alone, The Insatiable has its printed 321 HP", boss.max_hp == 321, boss.max_hp)
c, a, (boss,) = fight("theinsatiable", players=2, act="act2", scale=True)
check("two players in act 2: 321 x 2 x 1.2 = 770", boss.max_hp == 770, boss.max_hp)
c, a, (boss,) = fight("theinsatiable", players=3, act="act3boss", scale=True)
check("three players, act 3 boss: 321 x 3 x 1.3 = 1252", boss.max_hp == 1252, boss.max_hp)
c, a, (boss,) = fight("aeonglass", players=2, scale=True)
check("Aeonglass, two players, act 1: 512 x 2.2 = 1126", boss.max_hp == 1126, boss.max_hp)

dummy = create_enemy("dummy1", "e1", rng=random.Random(1))
base = dummy.max_hp
Combat([create_ally("testally1", "p1", rng=random.Random(1)),
        create_ally("testally1", "p2", rng=random.Random(1))],
       [dummy], rng=random.Random(1), act="act1").start()
check("the old test dummy scales too", dummy.max_hp == round(base * 2.2), (base, dummy.max_hp))

# ============================================================================
# the fixed patterns: (move, HP lost per player, Block after, Strength after)
# ============================================================================
SCRIPTS = {
    "nibbit": [("Butt", [12], 0, 0), ("Hesitant Slice", [6], 5, 0), ("Hiss", [0], 0, 2),
               ("Butt", [14], 0, 2), ("Hesitant Slice", [8], 5, 2), ("Hiss", [0], 0, 4)],
    "snappingjaxfruit": [("Energy Orb", [3], 0, 2), ("Energy Orb", [5], 0, 4),
                         ("Energy Orb", [7], 0, 6)],
    "fuzzywurmcrawler": [("Acid Goop", [4], 0, 0), ("Inhale", [0], 0, 7), ("Acid Goop", [11], 0, 7),
                         ("Acid Goop", [11], 0, 7), ("Inhale", [0], 0, 14), ("Acid Goop", [18], 0, 14)],
    "assassinraider": [("Killshot", [10], 0, 0)] * 3,
    "axeraider": [("Swing", [5], 5, 0), ("Swing", [5], 5, 0), ("Big Swing", [12], 0, 0),
                  ("Swing", [5], 5, 0)],
    "bruteraider": [("Beat", [7], 0, 0), ("Roar", [0], 0, 3), ("Beat", [10], 0, 3),
                    ("Roar", [0], 0, 6)],
    "crossbowraider": [("Reload", [0], 3, 0), ("Fire!", [14], 0, 0), ("Reload", [0], 3, 0)],
    "trackerraider": [("Track", [0], 0, 0), ("Unleash the Hounds", [8], 0, 0),
                      ("Unleash the Hounds", [8], 0, 0), ("Unleash the Hounds", [8], 0, 0)],
    # Charge Up 2, then +2 after every Repeater Blast; Expel is 5 + Strength, twice
    "cubexconstruct": [("Charge Up", [0], 0, 2), ("Repeater Blast", [9], 0, 4),
                       ("Repeater Blast", [11], 0, 6), ("Expel Blast", [22], 0, 6),
                       ("Repeater Blast", [13], 0, 8)],
    "vineshambler": [("Swipe", [12], 0, 0), ("Grasping Vines", [8], 0, 0), ("Chomp", [16], 0, 0),
                     ("Swipe", [12], 0, 0)],
    "shrinkerbeetle": [("Shrinker", [0], 0, 0), ("Chomp", [7], 0, 0), ("Stomp", [13], 0, 0),
                       ("Chomp", [7], 0, 0)],
    "leafslimemedium": [("Sticky Shot", [0], 0, 0), ("Clump Shot", [8], 0, 0),
                        ("Sticky Shot", [0], 0, 0), ("Clump Shot", [8], 0, 0)],
    "twigslimesmall": [("Tackle", [4], 0, 0)] * 3,
    "wriggler": [("Nasty Bite", [6], 0, 0), ("Wriggle", [0], 0, 2), ("Nasty Bite", [8], 0, 2),
                 ("Wriggle", [0], 0, 4)],
}
for kind, script in SCRIPTS.items():
    got = play_out(kind, len(script))
    check("%s: %s" % (kind, " / ".join(m for m, _, _, _ in script)),
          got == script, [(g, s) for g, s in zip(got, script) if g != s])

HP_RANGES = {"nibbit": (42, 46), "snappingjaxfruit": (31, 33), "fuzzywurmcrawler": (55, 57),
             "assassinraider": (18, 23), "axeraider": (20, 22), "bruteraider": (30, 33),
             "crossbowraider": (18, 21), "trackerraider": (21, 25), "flyconid": (47, 49),
             "slitheringstrangler": (53, 55), "shrinkerbeetle": (38, 40), "leafslimesmall": (11, 15),
             "leafslimemedium": (32, 35), "twigslimesmall": (7, 11), "twigslimemedium": (26, 28),
             "wriggler": (17, 21), "cubexconstruct": (65, 65), "vineshambler": (61, 61),
             "mawler": (72, 72), "aeonglass": (512, 512), "theinsatiable": (321, 321)}
for kind, (lo, hi) in HP_RANGES.items():
    rolled = {create_enemy(kind, "e1", rng=random.Random(s)).max_hp for s in range(60)}
    check("%s HP %d-%d" % (kind, lo, hi), min(rolled) == lo and max(rolled) == hi, sorted(rolled))

# where a pattern starts depends on the encounter, as in the game
c, a, foes = fight(["nibbit", "nibbit"])
check("two Nibbits: the front one Slices first, the back one Hisses first",
      [f.intent["name"] for f in foes] == ["Hesitant Slice", "Hiss"],
      [f.intent["name"] for f in foes])
c, a, foes = fight(["wriggler"] * 4)
check("four Wrigglers: slots 1 and 3 bite first, 2 and 4 wriggle first",
      [f.intent["name"] for f in foes] == ["Nasty Bite", "Wriggle", "Nasty Bite", "Wriggle"],
      [f.intent["name"] for f in foes])

# ============================================================================
# the random ones: the game's repeat rules, over many fights
# ============================================================================
def runs(kind, turns=10, seeds=40):
    return [moves(kind, turns, seed) for seed in range(seeds)]

def repeats(seq, n):
    """True if some move appears more than n times running."""
    return any(len(set(seq[i:i + n + 1])) == 1 for i in range(len(seq) - n))

seqs = runs("leafslimesmall")
check("Leaf Slime (S) opens with either move", {s[0] for s in seqs} == {"Tackle", "Goop"},
      {s[0] for s in seqs})
check("...and never uses one twice running", not any(repeats(s, 1) for s in seqs))

seqs = runs("twigslimemedium")
check("Twig Slime (M) always opens with Sticky Shot", all(s[0] == "Sticky Shot" for s in seqs))
check("...never two Sticky Shots running",
      not any(s[i] == s[i + 1] == "Sticky Shot" for s in seqs for i in range(len(s) - 1)))
check("...Pokey Pounce at most twice running",
      not any(s[i] == s[i + 1] == s[i + 2] == "Pokey Pounce" for s in seqs for i in range(len(s) - 2)))
check("...and it does pounce twice running sometimes",
      any(s[i] == s[i + 1] == "Pokey Pounce" for s in seqs for i in range(len(s) - 1)))

seqs = runs("flyconid")
check("Flyconid never opens with Vulnerable Spores",
      {s[0] for s in seqs} == {"Frail Spores", "Smash"}, {s[0] for s in seqs})
check("...Frail Spores never within 2 moves of the last one",
      not any("Frail Spores" in s[i + 1:i + 3] for s in seqs for i, m in enumerate(s) if m == "Frail Spores"))
check("...and it does use Vulnerable Spores", any("Vulnerable Spores" in s for s in seqs))

seqs = runs("slitheringstrangler")
check("Slithering Strangler Constricts every other turn",
      all(s[i] == "Constrict" for s in seqs for i in range(0, len(s), 2)))
check("...with Thwack or Lash at random in between",
      {s[i] for s in seqs for i in range(1, len(s), 2)} == {"Thwack", "Lash"})
c, a, (foe,) = fight("slitheringstrangler")
pass_turn(c, a); pass_turn(c, a); pass_turn(c, a)
check("...and its Constrict stacks: 3 + 3 = 6", charges(a[0], "constrict") == 6, charges(a[0], "constrict"))

seqs = runs("mawler")
check("Mawler opens with Claw", all(s[0] == "Claw" for s in seqs))
check("...Roars at most once a fight", all(s.count("Roar") <= 1 for s in seqs))
check("...never Claws or Rips twice running",
      not any(s[i] == s[i + 1] and s[i] != "Roar" for s in seqs for i in range(len(s) - 1)))
check("...and does Roar in some fights", any("Roar" in s for s in seqs))

check("an enemy's moves do not depend on how many players there are",
      moves("flyconid", 8, 5) == [m for m in moves("flyconid", 8, 5)]
      and play_out("mawler", 6, players=1, seed=4)[0][0] == play_out("mawler", 6, players=3, seed=4)[0][0])
names_1p = [r[0] for r in play_out("flyconid", 8, players=1, seed=6)]
names_3p = [r[0] for r in play_out("flyconid", 8, players=3, seed=6)]
check("...Flyconid picks the same moves for one player or three (its own rng)",
      names_1p == names_3p, (names_1p, names_3p))

# ============================================================================
# Artifact: Cubex and Aeonglass
# ============================================================================
c, a, (cubex,) = fight("cubexconstruct")
check("Cubex arrives behind 13 Block with 1 Artifact",
      cubex.block == 13 and charges(cubex, "artifact") == 1, (cubex.block, charges(cubex, "artifact")))
c, a, (cubex,) = fight("cubexconstruct", players=2, scale=True)
check("...two players: 26 Block (co-op Block scaling) and 2 Artifact",
      cubex.block == 26 and charges(cubex, "artifact") == 2, (cubex.block, charges(cubex, "artifact")))

c, a, (cubex,) = fight("cubexconstruct")
a[0].energy = 9
a[0].hand = [CardRef("bash")]
c.play_card(a[0], 0, target=cubex)
check("Artifact eats Bash's Vulnerable, and is spent",
      cubex.get_status("vulnerable") is None and charges(cubex, "artifact") == 0,
      (cubex.statuses.keys(), charges(cubex, "artifact")))
a[0].hand = [CardRef("bash")]
c.play_card(a[0], 0, target=cubex)
check("...so the second Bash's Vulnerable lands", charges(cubex, "vulnerable") == 2)
c, a, (cubex,) = fight("cubexconstruct")
cubex.apply_status(Strength(source=cubex, target=cubex, amount=1))
check("a buff is not a debuff: Artifact untouched", charges(cubex, "artifact") == 1)

# ============================================================================
# statuses the enemies bring
# ============================================================================
c, a, (beetle,) = fight("shrinkerbeetle", players=2)
pass_turn(c, a)
check("Shrinker Beetle Shrinks every player, permanently (-1)",
      [charges(p, "shrink") for p in a] == [-1, -1], [charges(p, "shrink") for p in a])
for _ in range(4):
    pass_turn(c, a)
check("...and it never wears off", [charges(p, "shrink") for p in a] == [-1, -1])
a[0].energy = 9
a[0].hand = [CardRef("strike")]
hp = beetle.current_hp
c.play_card(a[0], 0, target=beetle)
check("...a Strike deals 6 x 0.7 = 4", hp - beetle.current_hp == 4, hp - beetle.current_hp)
beetle.current_hp = 0
pass_turn(c, a)
check("...until the Beetle dies", all(p.get_status("shrink") is None for p in a),
      [list(p.statuses) for p in a])

# ============================================================================
# The Insatiable
# ============================================================================
c, a, (boss,) = fight("theinsatiable", players=2)
check("turn 1 is Liquify Ground", boss.intent["name"] == "Liquify Ground")
ctx = c._context_for(boss)
for effect in boss._liquify(ctx):
    c._resolve(effect)
check("Liquify: 4 Sandpit on each player", [charges(p, "sandpit") for p in a] == [4, 4])
check("...3 Frantic Escape in each draw pile, 3 in each discard",
      all(p.draw_pile.count("frantic_escape") == 3 and p.discard_pile.count("frantic_escape") == 3
          for p in a))
depths = set()
for seed in range(20):
    c, a, (boss,) = fight("theinsatiable", seed=seed)
    for effect in boss._liquify(c._context_for(boss)):
        c._resolve(effect)
    depths.update(i for i, r in enumerate(a[0].draw_pile) if r == "frantic_escape")
check("...shuffled in at random depths, not all at the bottom", depths - {0, 1, 2}, sorted(depths))

check("the cycle: Liquify, Thrash, Lunging Bite, Salivate, Thrash, Thrash, Lunging Bite, Salivate",
      moves("theinsatiable", 8, 1) == ["Liquify Ground", "Thrash", "Lunging Bite", "Salivate",
                                       "Thrash", "Thrash", "Lunging Bite", "Salivate"],
      moves("theinsatiable", 8, 1))
c, a, (boss,) = fight("theinsatiable", players=2)
pass_turn(c, a)                                           # Liquify
hp = [p.current_hp for p in a]
pass_turn(c, a)                                           # Thrash 8 x 2
check("Thrash hits both players twice for 8", [h - p.current_hp for h, p in zip(hp, a)] == [16, 16])

# Sandpit counts down at the start of each ENEMY turn, as in the game
c, a, (boss,) = fight("theinsatiable", players=2, ally_hp=5000)
seen = []
for _ in range(4):
    pass_turn(c, a, keep=("sandpit",))
    seen.append([charges(p, "sandpit") for p in a])
check("Sandpit: 4 after Liquify, then 3, 2, 1 at the start of each enemy turn",
      seen == [[4, 4], [3, 3], [2, 2], [1, 1]], seen)
check("...so with 1 left the players still get this whole turn", not c.is_over())
pass_turn(c, a, keep=("sandpit",))
check("...and are eaten as the next enemy turn begins: DEFEAT with 5000 HP",
      c.is_over() and c.result.name == "DEFEAT", (c.result, [p.current_hp for p in a]))

c, a, (boss,) = fight("theinsatiable", ally_hp=5000)
pass_turn(c, a, keep=("sandpit",))
a[0].energy = 9
a[0].hand = [CardRef("frantic_escape")]
c.play_card(a[0], 0)
check("a Frantic Escape adds a turn to the Sandpit: 4 -> 5", charges(a[0], "sandpit") == 5,
      charges(a[0], "sandpit"))

# ============================================================================
# Aeonglass
# ============================================================================
c, a, (glass,) = fight("aeonglass", players=2)
check("Aeonglass arrives with 3 Artifact, +1 for the second player", charges(glass, "artifact") == 4,
      charges(glass, "artifact"))
check("...and Withering Presence (6 cards) on every player",
      [charges(p, "withering_presence") for p in a] == [6, 6])
hp = [p.current_hp for p in a]
pass_turn(c, a)
check("Ebb: 26 to every player, and 33 Block (unscaled)",
      [h - p.current_hp for h, p in zip(hp, a)] == [26, 26] and glass.block == 33,
      ([h - p.current_hp for h, p in zip(hp, a)], glass.block))
hp = [p.current_hp for p in a]
pass_turn(c, a)
check("Eye Lasers: 11 x 2 to every player", [h - p.current_hp for h, p in zip(hp, a)] == [22, 22])

c, a, (glass,) = fight("aeonglass", players=2, ally_hp=5000)
def withers(p):
    return sorted(r.bonus_damage for pile in (p.hand, p.draw_pile, p.discard_pile, p.exhaust_pile)
                  for r in pile if r == "wither")
got = []
for turn in range(9):
    intensity = glass.intent["name"] == "Increasing Intensity"
    c.end_player_turn()          # hands go to the discard, not away: Withers drawn must stay
    if intensity:
        got.append((charges(glass, "strength"), withers(a[0]), withers(a[1])))
check("Increasing Intensity: +3, +4, +5 Strength (3, 7, 12)",
      [g[0] for g in got] == [3, 7, 12], [g[0] for g in got])
check("...and every time, all Withers go up one level (+3) and a new one arrives at that level",
      [g[1] for g in got] == [[3], [6, 6], [9, 9, 9]] and [g[2] for g in got] == [[3], [6, 6], [9, 9, 9]],
      got)

c, a, (glass,) = fight("aeonglass")
a[0].hand = [CardRef("wither", bonus_damage=3)]
glass.get_effects = lambda context: []
hp = a[0].current_hp
c.end_player_turn()
check("a Wither+1 held at the end of the turn deals 3 + 3 = 6", hp - a[0].current_hp == 6,
      hp - a[0].current_hp)

c, a, (glass,) = fight("aeonglass")
a[0].energy = 99
for n in range(6):
    a[0].hand = [CardRef("defend")] + [r for r in a[0].hand if r == "wither"]
    c.play_card(a[0], 0)
check("Withering Presence: the 6th card played puts a Wither in hand",
      a[0].hand.count("wither") == 1, a[0].hand)
check("...and starts counting 6 again", charges(a[0], "withering_presence") == 6)

c, a, (glass,) = fight("aeonglass")
a[0].energy = 9
a[0].hand = [CardRef("bash")]
c.play_card(a[0], 0, target=glass)
check("its Artifact eats Bash's Vulnerable", glass.get_status("vulnerable") is None
      and charges(glass, "artifact") == 2, (list(glass.statuses), charges(glass, "artifact")))

# ============================================================================
# the party cap: co-op is one to four players
# ============================================================================
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

# ============================================================================
# summoning: InstantSummon goes to Combat, which owns the ids and the scaling
# ============================================================================
from GameEngine.Effects.InstantEffects.instant_summon import InstantSummon

c = Combat(party(2), [create_enemy("dummy1", "e1", rng=random.Random(1))], rng=random.Random(1))
c.start()
leader = c.enemies[0]
result = c._resolve(InstantSummon(source=leader, type_ids=["dummy1"], stunned=True, minion=True))
new = c.find_unit("e2")
check("a summon resolves instead of raising: e2 arrives, and the result says so",
      new is not None and result["summoned"] == ["e2"] and result["amount"] == 1, result)
scaled = {round(hp * 2.2) for hp in range(18, 23)}       # Dummy's 20 +/- 2, two players in act 1
check("it arrives scaled for two players, with an intent, led by its summoner",
      new.max_hp in scaled and new.intent is not None and new.leader is leader,
      (new.max_hp, sorted(scaled), new.intent))
check("stunned and a Minion when asked", new.get_status("stun") is not None
      and new.get_status("minion") is not None, list(new.statuses))
leader.current_hp = 0
c._resolve_deaths()
check("a Minion leaves when its leader dies", not new.is_alive())

# ============================================================================
# HP rolled as an enemy enters, unlike the others: SetUniqueMonsterHpValue
# ============================================================================
def lineup_hps(players, seed, kinds=("nibbit", "nibbit", "nibbit")):
    s = Session(combat_factory=Combat, required_players=players, seed=seed)
    s.ENEMY_TYPE_IDS = kinds
    s.SCALE_ENEMIES = True
    for i in range(players):
        s.add_player("s%d" % i)
    return [e.max_hp for e in s.combat.enemies]

solo = [lineup_hps(1, seed) for seed in range(60)]
check("alone, three Nibbits (42-46) never share an HP", all(len(set(h)) == 3 for h in solo),
      [h for h in solo if len(set(h)) < 3][:3])
check("and every value in the range turns up", set().union(*map(set, solo)) == set(range(42, 47)))
duo = [lineup_hps(2, seed) for seed in range(60)]
check("two players: each rolled against the others' scaled HP, so two can match, as in the game",
      any(len(set(h)) < 3 for h in duo) and all(92 <= hp <= 101 for h in duo for hp in h),
      duo[:3])
c = Combat(party(1), [create_enemy("wriggler", "e1")], rng=random.Random(4))
c.start()
for _ in range(4):
    c._resolve(InstantSummon(source=c.enemies[0], type_ids=["wriggler"]))
hps = sorted(e.max_hp for e in c.enemies)
check("five Wrigglers (17-21) summoned one by one: all five values", hps == [17, 18, 19, 20, 21], hps)
built = create_enemy("nibbit", "e1", rng=random.Random(3))
c = Combat(party(1), [built], rng=random.Random(1), scale_enemies=False)
before = built.max_hp
c.start()
check("an enemy built with its own rng keeps what it rolled", built.max_hp == before, (before, built.max_hp))

print()
print("%d checks failed" % len(bad))
for label in bad:
    print("   ", label)

import sys as _sys
_sys.exit(1 if bad else 0)
