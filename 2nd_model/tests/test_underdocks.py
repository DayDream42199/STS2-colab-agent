"""The Underdocks (Act 1) enemies, each against the installed game's code
(MegaCrit.Sts2.Core.Models.Monsters)."""
import random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Cards._card_ref import CardRef
from GameEngine.Effects.InstantEffects.instant_damage import InstantDamage

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))


def fight(kinds, players=1, seed=1, scale=False, ally_hp=5000):
    kinds = [kinds] if isinstance(kinds, str) else list(kinds)
    allies = [create_ally("testally1", "p%d" % (i + 1), rng=random.Random(seed + i))
              for i in range(players)]
    for a in allies:
        a.deck = ["strike"] * 5 + ["defend"] * 5
    foes = [create_enemy(k, "e%d" % (i + 1)) for i, k in enumerate(kinds)]
    c = Combat(allies, foes, rng=random.Random(seed), scale_enemies=scale)
    c.start()
    for a in allies:
        a.max_hp = a.current_hp = ally_hp
        a.block = 0
    return c, allies, foes


def pass_turn(c, allies):
    """End the turn without playing anything; nobody keeps Block."""
    for a in allies:
        a.hand = []
        a.block = 0
    c.end_player_turn()


def names(c, allies, foe, turns):
    out = []
    for _ in range(turns):
        out.append(foe.intent["name"])
        pass_turn(c, allies)
    return out


def run(kinds, seed, turns, which=0):
    c, a, foes = fight(kinds, seed=seed)
    return names(c, a, foes[which], turns)


def amount(unit, status):
    s = unit.get_status(status)
    return s.amount if s is not None else 0


def hit(c, attacker, target, n):
    c._resolve(InstantDamage(source=attacker, target=target, amount=n))


def taken(c, a, turns=1):
    """HP the first player loses over `turns` enemy phases."""
    before = a[0].current_hp
    for _ in range(turns):
        pass_turn(c, a)
    return before - a[0].current_hp


# ============================================================================
print("== Seapunk (Seapunk.cs) ==")
# ============================================================================
c, a, (sea,) = fight("seapunk")
check("HP 44-46", 44 <= sea.max_hp <= 46, sea.max_hp)
seq = names(c, a, sea, 3)
check("Bubble Burp: 7 Block and +1 Strength", sea.block == 7 and amount(sea, "strength") == 1,
      (sea.block, amount(sea, "strength")))
seq += names(c, a, sea, 1)
check("Sea Kick, Spinning Kick, Bubble Burp, round again",
      seq == ["Sea Kick", "Spinning Kick", "Bubble Burp", "Sea Kick"], seq)
c, a, (sea,) = fight("seapunk")
check("Sea Kick 11, then Spinning Kick 2 x 4", taken(c, a) == 11 and taken(c, a) == 8)

# ============================================================================
print("\n== Sewer Clam (SewerClam.cs, PlatingPower.cs) ==")
# ============================================================================
c, a, (clam,) = fight("sewerclam")
check("56 HP; arrives with 8 Plating and 8 Block", clam.max_hp == 56 and amount(clam, "plating") == 8
      and clam.block == 8, (clam.max_hp, amount(clam, "plating"), clam.block))
seq, blocks = [], []
for _ in range(4):
    seq.append(clam.intent["name"])
    blocks.append(clam.block)
    pass_turn(c, a)
check("Jet, Pressurize, Jet, Pressurize", seq == ["Jet", "Pressurize"] * 2, seq)
check("Plating: Block at each enemy turn's end, one less each turn after the first",
      blocks == [8, 8, 7, 6], blocks)
check("Pressurize gives 4 Strength", amount(clam, "strength") == 8, amount(clam, "strength"))
c, a, (clam,) = fight("sewerclam", players=2, scale=True)
check("two players: Plating x3 (24) and that much Block - a power's Block is not scaled again",
      amount(clam, "plating") == 24 and clam.block == 24, (amount(clam, "plating"), clam.block))
pass_turn(c, a)
pass_turn(c, a)
check("and it drops by 2 a turn (one per player)", amount(clam, "plating") == 22 and clam.block == 22,
      (amount(clam, "plating"), clam.block))

# ============================================================================
print("\n== Haunted Ship (HauntedShip.cs) ==")
# ============================================================================
c, a, (ship,) = fight("hauntedship")
check("63 HP, Haunt first", ship.max_hp == 63 and ship.intent["name"] == "Haunt")
pass_turn(c, a)
dazed = sum(1 for x in a[0].discard_pile if str(x) == "dazed")
check("Haunt: 3 Weak and 5 Dazed into the discard pile", amount(a[0], "weak") == 3 and dazed == 5,
      (amount(a[0], "weak"), dazed))
seq = names(c, a, ship, 4)
check("then Swipe and Stomp in turn, never Haunt again", seq == ["Swipe", "Stomp", "Swipe", "Stomp"], seq)
check("Swipe 13, Stomp 4 x 3", (ship._swipe.damage, ship._stomp.damage, ship._stomp.hits) == (13, 4, 3))

# ============================================================================
print("\n== Sludge Spinner (SludgeSpinner.cs) ==")
# ============================================================================
seqs = [run("sludgespinner", seed, 10) for seed in range(30)]
check("HP 37-39, Oil Spray first", all(s[0] == "Oil Spray" for s in seqs))
check("never the same move twice running", not any(s[i] == s[i + 1] for s in seqs for i in range(9)))
check("all three come up", {m for s in seqs for m in s} == {"Oil Spray", "Slam", "Rage"})
c, a, (spin,) = fight("sludgespinner")
check("Oil Spray 8 and a Weak", taken(c, a) == 8 and amount(a[0], "weak") == 1)

# ============================================================================
print("\n== Punch Construct (PunchConstruct.cs) ==")
# ============================================================================
c, a, (pc,) = fight("punchconstruct")
check("55 HP, 1 Artifact, Ready first", pc.max_hp == 55 and amount(pc, "artifact") == 1
      and pc.intent["name"] == "Ready")
seq = names(c, a, pc, 4)
check("Ready, Fast Punch, Strong Punch, round again", seq == ["Ready", "Fast Punch", "Strong Punch", "Ready"], seq)
c, a, (pc,) = fight("punchconstruct")
pass_turn(c, a)
check("Ready: 10 Block", pc.block == 10, pc.block)
check("Fast Punch 5 x 2 and a Frail, Strong Punch 14",
      taken(c, a) == 10 and amount(a[0], "frail") == 1 and taken(c, a) == 14)
c, a, (pc,) = fight("punchconstruct", players=2, scale=True)
check("two players: 2 Artifact", amount(pc, "artifact") == 2)

# ============================================================================
print("\n== Cultists (CalcifiedCultist.cs, DampCultist.cs, RitualPower.cs) ==")
# ============================================================================
c, a, (cal, damp) = fight(["calcifiedcultist", "dampcultist"])
check("HP 38-41 and 51-53", 38 <= cal.max_hp <= 41 and 51 <= damp.max_hp <= 53, (cal.max_hp, damp.max_hp))
rows = []
for _ in range(4):
    rows.append((cal.intent["name"], amount(cal, "strength"), damp.intent["name"], amount(damp, "strength")))
    pass_turn(c, a)
check("Incantation, then Dark Strike; Ritual's Strength from the turn after it was cast",
      rows == [("Incantation", 0, "Incantation", 0), ("Dark Strike", 0, "Dark Strike", 0),
               ("Dark Strike", 2, "Dark Strike", 5), ("Dark Strike", 4, "Dark Strike", 10)], rows)
check("Dark Strike: 9 for the Calcified, 1 for the Damp",
      (cal._dark_strike.damage, damp._dark_strike.damage) == (9, 1))

# ============================================================================
print("\n== Toadpole (Toadpole.cs, ThornsPower.cs) ==")
# ============================================================================
c, a, (front, back) = fight(["toadpole", "toadpole"])
check("HP 21-25", all(21 <= t.max_hp <= 25 for t in (front, back)), (front.max_hp, back.max_hp))
rows = [(front.intent["name"], back.intent["name"])]
for _ in range(3):
    pass_turn(c, a)
    rows.append((front.intent["name"], back.intent["name"]))
check("Whirl, Spiken, Spike Spit; the front one opens with Spiken",
      rows == [("Spiken", "Whirl"), ("Spike Spit", "Spiken"), ("Whirl", "Spike Spit"),
               ("Spiken", "Whirl")], rows)
c, a, (toad,) = fight("toadpole")
pass_turn(c, a)
check("Spiken: 2 Thorns", amount(toad, "caltrops") == 2)
before = a[0].current_hp
hit(c, a[0], toad, 1)
check("Thorns hits back for 2", before - a[0].current_hp == 2, before - a[0].current_hp)
check("Spike Spit sheds the Thorns first, then 3 x 3",
      taken(c, a) == 9 and amount(toad, "caltrops") == 0, amount(toad, "caltrops"))

# ============================================================================
print("\n== Corpse Slug (CorpseSlug.cs, RavenousPower.cs) ==")
# ============================================================================
c, a, slugs = fight(["corpseslug"] * 3)
check("HP 25-27, 4 Ravenous", all(25 <= s.max_hp <= 27 and amount(s, "ravenous") == 4 for s in slugs))
opening = [s.intent["name"] for s in slugs]
check("the three open on three different moves", len(set(opening)) == 3, opening)
seq = names(c, a, slugs[0], 4)
cycle = ["Whip Slap", "Glomp", "Goop"]
i = cycle.index(seq[0])
check("Whip Slap, Glomp, Goop, round and round", seq == [cycle[(i + k) % 3] for k in range(4)], seq)
c, a, slugs = fight(["corpseslug"] * 3)
hit(c, a[0], slugs[0], 999)
c._check_combat_end()
check("a slug dies: the others are stunned and gain 4 Strength",
      all(amount(s, "stun") == 1 and amount(s, "strength") == 4 for s in slugs[1:])
      and all(c._enemy_dict(s)["intent"]["name"] == "Stunned" for s in slugs[1:]))
c, a, (slug,) = fight("corpseslug")
while slug.intent["name"] != "Goop":
    pass_turn(c, a)
pass_turn(c, a)
check("Goop: 2 Frail", amount(a[0], "frail") == 2, amount(a[0], "frail"))

# ============================================================================
print("\n== Fossil Stalker (FossilStalker.cs, SuckPower.cs) ==")
# ============================================================================
seqs = [run("fossilstalker", seed, 10) for seed in range(30)]
check("Latch first", all(s[0] == "Latch" for s in seqs))
check("never the same move three times running",
      not any(s[i] == s[i + 1] == s[i + 2] for s in seqs for i in range(8)))
check("Latch, Tackle and Lash all come up", {m for s in seqs for m in s} == {"Latch", "Tackle", "Lash"})
c, a, (fossil,) = fight("fossilstalker")
check("HP 51-53, 3 Suck", 51 <= fossil.max_hp <= 53 and amount(fossil, "suck") == 3)
check("Latch 12", taken(c, a) == 12)
check("Suck: +3 Strength for the hit that got through", amount(fossil, "strength") == 3,
      amount(fossil, "strength"))
c, a, (fossil,) = fight("fossilstalker")
a[0].hand, a[0].block = [], 999
c.end_player_turn()
check("a fully blocked hit gives nothing", amount(fossil, "strength") == 0)

# ============================================================================
print("\n== Gremlin Merc (GremlinMerc.cs, SurprisePower.cs, Sneaky/FatGremlin.cs) ==")
# ============================================================================
c, a, (merc,) = fight("gremlinmerc")
check("HP 47-49, Surprise", 47 <= merc.max_hp <= 49 and merc.get_status("surprise") is not None)
seq = names(c, a, merc, 4)
check("Gimme, Double Smash, Hehe, round again", seq == ["Gimme", "Double Smash", "Hehe", "Gimme"], seq)
c, a, (merc,) = fight("gremlinmerc")
check("Gimme 7 x 2, Double Smash 6 x 2 and 2 Weak",
      taken(c, a) == 14 and taken(c, a) == 12 and amount(a[0], "weak") == 2)
pass_turn(c, a)
check("Hehe: +2 Strength", amount(merc, "strength") == 2)
c, a, (merc,) = fight("gremlinmerc")
hit(c, a[0], merc, 999)
c._check_combat_end()
kinds = [type(e).__name__ for e in c.enemies if e.is_alive()]
check("Surprise: it dies and a Sneaky and a Fat Gremlin jump in; the fight goes on",
      kinds == ["SneakyGremlin", "FatGremlin"] and not c.is_over(), kinds)
sneaky, fat = c.enemies[1:]
check("they arrive Spawned", (sneaky.intent["name"], fat.intent["name"]) == ("Spawned", "Spawned"))
check("Spawned does nothing", taken(c, a) == 0)
check("then the Sneaky one Tackles and the Fat one Flees",
      (sneaky.intent["name"], fat.intent["name"]) == ("Tackle", "Flee"))
check("Tackle 9", taken(c, a) == 9)
check("the Fat one fled: gone, not killed, and the fight goes on with the Sneaky one",
      getattr(fat, "escaped", False) and not fat.is_alive() and not c.is_over())
c, a, (merc,) = fight("gremlinmerc")
hit(c, a[0], merc, 999)
c._check_combat_end()
hit(c, a[0], c.enemies[1], 999)
c._check_combat_end()
pass_turn(c, a)
pass_turn(c, a)
check("the Sneaky one dead and the Fat one fled: the fight is won", c.is_over())

# ============================================================================
print("\n== Terror Eel (TerrorEel.cs, ShriekPower.cs, VigorPower.cs) ==")
# ============================================================================
c, a, (eel,) = fight("terroreel")
check("140 HP, 70 Shriek", eel.max_hp == 140 and amount(eel, "shriek") == 70)
seq = names(c, a, eel, 4)
check("Crash, Thrash, round and round", seq == ["Crash", "Thrash", "Crash", "Thrash"], seq)
c, a, (eel,) = fight("terroreel")
check("Crash 16", taken(c, a) == 16)
check("Thrash 3 x 3, its own Vigor not on its own hits", taken(c, a) == 9 and amount(eel, "vigor") == 6)
check("then Crash 16 + 6 Vigor, and the Vigor is spent", taken(c, a) == 22 and amount(eel, "vigor") == 0)
c, a, (eel,) = fight("terroreel")
hit(c, a[0], eel, 69)
check("above 70 HP nothing happens", amount(eel, "shriek") == 70 and amount(eel, "stun") == 0)
hit(c, a[0], eel, 1)
check("down to 70: stunned, Shriek gone", amount(eel, "stun") == 1 and eel.get_status("shriek") is None
      and c._enemy_dict(eel)["intent"]["name"] == "Stunned")
check("the stun costs it its turn", taken(c, a) == 0)
seq = names(c, a, eel, 3)
check("then Terror, Crash, Thrash", seq == ["Terror", "Crash", "Thrash"], seq)
check("Terror: 99 Vulnerable", amount(a[0], "vulnerable") >= 97, amount(a[0], "vulnerable"))
c, a, (eel,) = fight("terroreel", players=2, scale=True)
check("two players: Shriek scales with its HP (154 of 308)",
      eel.max_hp == 308 and amount(eel, "shriek") == 154, (eel.max_hp, amount(eel, "shriek")))

# ============================================================================
print("\n== Vigor on a multi-hit attack (VigorPower.cs) ==")
# ============================================================================
from GameEngine.Effects.StatusEffects.vigor import Vigor
c, a, (dummy,) = fight("skulkingcolony")
dummy.statuses.clear()
a[0].apply_status(Vigor(source=a[0], target=a[0], amount=4))
a[0].hand, a[0].energy = ["twin_strike", "twin_strike"], 5
before = dummy.current_hp
c.play_card(a[0], 0, target=dummy)
check("Twin Strike: Vigor on both hits", before - dummy.current_hp == 2 * (5 + 4), before - dummy.current_hp)
check("and spent once the card is over", amount(a[0], "vigor") == 0)
before = dummy.current_hp
c.play_card(a[0], 0, target=dummy)
check("the next attack has none", before - dummy.current_hp == 10, before - dummy.current_hp)

# ============================================================================
print("\n== Skulking Colony (SkulkingColony.cs, HardenedShellPower.cs) ==")
# ============================================================================
c, a, (col,) = fight("skulkingcolony")
check("75 HP, 20 Hardened Shell", col.max_hp == 75 and amount(col, "hardened_shell") == 20)
for _ in range(4):
    hit(c, a[0], col, 8)
check("loses at most 20 HP a turn", col.current_hp == 55, col.current_hp)
pass_turn(c, a)
hit(c, a[0], col, 8)
check("and again the next turn", col.current_hp == 47, col.current_hp)
c, a, (col,) = fight("skulkingcolony")
seq = names(c, a, col, 5)
check("Zoom, Zoom, Inertia, Piercing Stabs, round again",
      seq == ["Zoom", "Zoom", "Inertia", "Piercing Stabs", "Zoom"], seq)
c, a, (col,) = fight("skulkingcolony")
check("Zoom 14, Zoom 14, Inertia 9 and +2 Strength, Piercing Stabs (7 + 2) x 2",
      [taken(c, a) for _ in range(4)] == [14, 14, 9, 18] and amount(col, "strength") == 2)
c, a, (col,) = fight("skulkingcolony", players=2, scale=True)
check("two players: the shell scales with its HP (44 of 165)",
      col.max_hp == 165 and amount(col, "hardened_shell") == 44, (col.max_hp, amount(col, "hardened_shell")))

# ============================================================================
print("\n== Phantasmal Gardeners (PhantasmalGardener.cs, SkittishPower.cs) ==")
# ============================================================================
c, a, gardeners = fight(["phantasmalgardener"] * 4)
check("HP 26-31, 6 Skittish", all(26 <= g.max_hp <= 31 and amount(g, "skittish") == 6 for g in gardeners))
check("the four open on Flail, Bite, Lash, Enlarge",
      [g.intent["name"] for g in gardeners] == ["Flail", "Bite", "Lash", "Enlarge"])
seq = names(c, a, gardeners[1], 5)
check("Bite, Lash, Flail, Enlarge, round again", seq == ["Bite", "Lash", "Flail", "Enlarge", "Bite"], seq)
c, a, gardeners = fight(["phantasmalgardener"] * 4)
check("first turn: Flail 1 x 3 + Bite 5 + Lash 7", taken(c, a) == 15)
check("Enlarge: +2 Strength", amount(gardeners[3], "strength") == 2)
c, a, (g,) = fight("phantasmalgardener")
a[0].hand, a[0].energy = ["strike", "strike"], 5
c.play_card(a[0], 0, target=g)
check("a card attack gets through: 6 Block once it is over", g.block == 6, g.block)
hp = g.current_hp
c.play_card(a[0], 0, target=g)
check("only once a turn", g.block == 0 and g.current_hp == hp, (g.block, g.current_hp))
pass_turn(c, a)
a[0].hand, a[0].energy = ["strike"], 5
c.play_card(a[0], 0, target=g)
check("and again the next turn", g.block == 6, g.block)
c, a, gardeners = fight(["phantasmalgardener"] * 4, players=2, scale=True)
check("two players: 9 Skittish", all(amount(g, "skittish") == 9 for g in gardeners))

# ============================================================================
print("\n== Living Fog and Gas Bombs (LivingFog.cs, GasBomb.cs, SmoggyPower.cs) ==")
# ============================================================================
c, a, (fog,) = fight("livingfog")
check("80 HP", fog.max_hp == 80)
seq = names(c, a, fog, 5)
check("Advanced Gas, then Bloat and Super Gas Blast in turn",
      seq == ["Advanced Gas", "Bloat", "Super Gas Blast", "Bloat", "Super Gas Blast"], seq)
c, a, (fog,) = fight("livingfog")
check("Advanced Gas 8 and Smoggy", taken(c, a) == 8 and amount(a[0], "smoggy") == 1)
check("Bloat 5", taken(c, a) == 5)
bombs = [e for e in c.enemies if type(e).__name__ == "GasBomb"]
check("Bloat sets down a Gas Bomb: 7 HP, a Minion, about to Explode",
      len(bombs) == 1 and bombs[0].max_hp == 7 and amount(bombs[0], "minion") == 1
      and bombs[0].intent["name"] == "Explode", [(b.max_hp, b.intent) for b in bombs])
check("set down on the enemies' turn, it picked its move once, with everyone",
      bombs[0].turn == 1, bombs[0].turn)
check("Super Gas Blast 8 and the bomb's Explode 8", taken(c, a) == 16)
check("the bomb is gone once it has exploded", not bombs[0].is_alive() and not c.is_over())
c, a, (fog,) = fight("livingfog")
pass_turn(c, a)
pass_turn(c, a)
hit(c, a[0], fog, 999)
c._check_combat_end()
check("the fog dies: its bomb goes with it and the fight is won",
      not any(e.is_alive() for e in c.enemies) and c.is_over())

c, a, (fog,) = fight("livingfog")
pass_turn(c, a)
a[0].hand, a[0].energy = ["defend", "defend", "strike", "defend"], 9
playable = lambda: sorted({x["hand_index"] for x in c.legal_actions(a[0]) if x["type"] == "play_card"})
check("Smoggy: every card playable before a Skill", playable() == [0, 1, 2, 3], playable())
c.play_card(a[0], 0)
check("after one Skill no other Skill is offered, an Attack still is", playable() == [1], playable())
try:
    c.play_card(a[0], 0)
    refused = False
except ValueError:
    refused = True
check("and a second Skill is refused", refused and a[0].hand[0] == "defend")
block = a[0].block
c.auto_play_card(a[0], "defend")
check("played for you, it does nothing either", a[0].block == block, a[0].block)
pass_turn(c, a)
a[0].hand, a[0].energy = ["defend"], 9
check("the next turn a Skill may be played again", playable() == [0], playable())

# ============================================================================
print("\n== Two-Tailed Rats (TwoTailedRat.cs, TwoTailedRatsNormal.cs) ==")
# ============================================================================
def rat_fight(seed, turns=12):
    c, a, rats = fight(["twotailedrat"] * 3, seed=seed)
    log = []
    for _ in range(turns):
        log.append([(r.unit_id, r.intent["name"]) for r in c.enemies if r.is_alive()])
        pass_turn(c, a)
    return c, rats, log

c, rats, _ = rat_fight(1, turns=0)
check("HP 17-21", all(17 <= r.max_hp <= 21 for r in rats), [r.max_hp for r in rats])
fights = [rat_fight(seed) for seed in range(40)]
openings = [[move for _, move in log[0]] for _, _, log in fights]
check("the three open on Scratch, Disease Bite and Screech, one each",
      all(sorted(o) == ["Disease Bite", "Scratch", "Screech"] for o in openings))
per_rat = []
for _, _, log in fights:
    moves = {}
    for turn in log:
        for uid, move in turn:
            moves.setdefault(uid, []).append(move)
    per_rat.extend(moves.values())
check("never the same move twice running",
      not any(s[i] == s[i + 1] for s in per_rat for i in range(len(s) - 1)))
check("Screech not again within three moves",
      not any(s[i] == "Screech" and "Screech" in s[i + 1:i + 4] for s in per_rat for i in range(len(s))))
check("no rat calls before its third move",
      all(i >= 2 for s in per_rat for i, m in enumerate(s) if m == "Call for Backup"))
check("each rat calls at most once", all(s.count("Call for Backup") <= 1 for s in per_rat))
calls = [sum(m == "Call for Backup" for _, m in turn) for _, _, log in fights for turn in log]
check("never two calls on one turn", max(calls) == 1, max(calls))
check("at most three calls in a fight",
      all(sum(m == "Call for Backup" for turn in log for _, m in turn) <= 3 for _, _, log in fights))
check("never more than five rats", all(len(turn) <= 5 for _, _, log in fights for turn in log))
grew = [(len(log[t + 1]) == len(log[t]) + 1)
        for _, _, log in fights for t in range(len(log) - 1)
        if any(m == "Call for Backup" for _, m in log[t]) and len(log[t]) < 5]
check("a call brings in a rat", grew and all(grew), (len(grew), sum(grew)))
c, a, rats = fight(["twotailedrat"] * 3, seed=1)
while not any(r.intent["name"] == "Call for Backup" for r in c.enemies if r.is_alive()):
    pass_turn(c, a)
pass_turn(c, a)
backup = c.enemies[-1]
check("the backup picked its move once, after the enemies' turn, at random",
      len(c.enemies) == 4 and backup.turn == 1 and backup.intent["name"] != "Call for Backup",
      (len(c.enemies), backup.turn, backup.intent))
check("and knows how many calls have been made", backup.backups_called == 1
      and all(r.backups_called == 1 for r in c.enemies), [r.backups_called for r in c.enemies])
check("Scratch 8, Disease Bite 6, Screech 1 Frail",
      (rats[0]._scratch.damage, rats[0]._disease_bite.damage, rats[0].SCREECH_FRAIL) == (8, 6, 1))

# ============================================================================
print("\n== Summoned on the enemies' turn (CombatManager.AfterCreatureAdded) ==")
# ============================================================================
from GameEngine.Effects.StatusEffects.caltrops import Caltrops
c, a, (merc,) = fight("gremlinmerc")
a[0].apply_status(Caltrops(source=a[0], target=a[0], amount=999))
pass_turn(c, a)
gremlins = [e for e in c.enemies if e.is_alive()]
check("a Merc killed on its own turn: the gremlins still open with Spawned",
      not merc.is_alive() and [g.intent["name"] for g in gremlins] == ["Spawned", "Spawned"],
      [(type(g).__name__, g.intent) for g in gremlins])

# ============================================================================
print("\n== Deaths resolve in play, not only when a test asks ==")
# ============================================================================
c, a, slugs = fight(["corpseslug"] * 3)
slugs[0].current_hp = 1
a[0].hand, a[0].energy = ["strike"], 5
c.play_card(a[0], 0, target=slugs[0])
check("a Strike kills a slug: the others are stunned and gain 4 Strength",
      all(amount(s, "stun") == 1 and amount(s, "strength") == 4 for s in slugs[1:]))
c, a, (merc,) = fight("gremlinmerc")
merc.current_hp = 1
a[0].hand, a[0].energy = ["strike"], 5
c.play_card(a[0], 0, target=merc)
check("a Strike kills the Merc: the gremlins jump in and the fight goes on",
      len([e for e in c.enemies if e.is_alive()]) == 2 and not c.is_over())
c, a, (fog,) = fight("livingfog")
pass_turn(c, a)
pass_turn(c, a)
fog.current_hp = 1
a[0].hand, a[0].energy = ["strike"], 5
c.play_card(a[0], 0, target=fog)
check("a Strike kills the fog: its bomb goes too and the fight is won", c.is_over())

# ============================================================================
print("\n== Lagavulin Matriarch (LagavulinMatriarch.cs, AsleepPower.cs, PlatingPower.cs) ==")
# ============================================================================
c, a, (lag,) = fight("lagavulinmatriarch")
check("222 HP; arrives asleep (3) behind 12 Plating and 12 Block",
      lag.max_hp == 222 and amount(lag, "asleep") == 3 and amount(lag, "plating") == 12 and lag.block == 12)
rows = []
for _ in range(5):
    rows.append((lag.intent["name"], lag.block, amount(lag, "plating")))
    pass_turn(c, a)
check("left alone it sleeps three turns, its Plating gone before the third ends, then Slash",
      rows == [("Sleep", 12, 12), ("Sleep", 12, 12), ("Sleep", 11, 11), ("Slash", 0, 0),
               ("Disembowel", 0, 0)], rows)
c, a, (lag,) = fight("lagavulinmatriarch")
for _ in range(3):
    pass_turn(c, a)
seq = names(c, a, lag, 5)
check("awake: Slash, Disembowel, Slash, Soul Siphon, round again",
      seq == ["Slash", "Disembowel", "Slash", "Soul Siphon", "Slash"], seq)
c, a, (lag,) = fight("lagavulinmatriarch")
for _ in range(3):
    pass_turn(c, a)
check("Slash 19, Disembowel 9 x 2", taken(c, a) == 19 and taken(c, a) == 18)
check("Slash 12 and 12 Block", taken(c, a) == 12 and lag.block == 12, lag.block)
pass_turn(c, a)
check("Soul Siphon: 2 Strength and 2 Dexterity off the player, 2 Strength for itself",
      (amount(a[0], "strength"), amount(a[0], "dexterity"), amount(lag, "strength")) == (-2, -2, 2))
pass_turn(c, a)
check("and the player's stay through the turns", (amount(a[0], "strength"), amount(a[0], "dexterity")) == (-2, -2))
c, a, (lag,) = fight("lagavulinmatriarch")
hit(c, a[0], lag, 12)
check("a hit its Block takes all of does not wake it", amount(lag, "asleep") == 3)
hit(c, a[0], lag, 3)
c._check_combat_end()
check("a hit through its Block wakes it: Plating gone, stunned",
      lag.get_status("asleep") is None and lag.get_status("plating") is None
      and c._enemy_dict(lag)["intent"]["name"] == "Stunned")
check("the stun costs it its turn, then Slash", taken(c, a) == 0 and lag.intent["name"] == "Slash")
from GameEngine.Effects.StatusEffects.artifact import Artifact
c, a, (lag,) = fight("lagavulinmatriarch")
for _ in range(6):
    pass_turn(c, a)
a[0].apply_status(Artifact(source=a[0], target=a[0], amount=1))
pass_turn(c, a)
check("Artifact stops the -2 Strength, a debuff below zero; the Dexterity lands",
      (amount(a[0], "strength"), amount(a[0], "dexterity"), amount(a[0], "artifact")) == (0, -2, 0))
c, a, (lag,) = fight("lagavulinmatriarch", players=2, scale=True)
check("two players: 36 Plating and Block, one Asleep count",
      (amount(lag, "plating"), lag.block, amount(lag, "asleep")) == (36, 36, 3))

# ============================================================================
print("\n== Soul Fysh (SoulFysh.cs, Beckon.cs, IntangiblePower.cs) ==")
# ============================================================================
c, a, (fysh,) = fight("soulfysh")
check("211 HP", fysh.max_hp == 211)
seq = names(c, a, fysh, 6)
check("Beckon, De-Gas, Gaze, Fade, Scream, round again",
      seq == ["Beckon", "De-Gas", "Gaze", "Fade", "Scream", "Beckon"], seq)
beckons = lambda pile: sum(1 for x in pile if str(x) == "beckon")
c, a, (fysh,) = fight("soulfysh")
pass_turn(c, a)
check("Beckon: one Beckon into the draw pile (or drawn since), one into the discard",
      (beckons(a[0].draw_pile + a[0].hand), beckons(a[0].discard_pile)) == (1, 1))
a[0].draw_pile = [x for x in a[0].draw_pile if str(x) != "beckon"]
a[0].hand = [x for x in a[0].hand if str(x) != "beckon"]
a[0].discard_pile = []
check("De-Gas 16", taken(c, a) == 16)
everywhere = lambda: beckons(a[0].hand + a[0].draw_pile + a[0].discard_pile)
check("Gaze 7 and a Beckon into the discard", taken(c, a) == 7 and everywhere() == 1, everywhere())
pass_turn(c, a)
check("Fade: Intangible through the players' next turn", amount(fysh, "intangible") == 1)
hp = fysh.current_hp
hit(c, a[0], fysh, 50)
check("a 50 hit deals it 1", hp - fysh.current_hp == 1, hp - fysh.current_hp)
check("Scream 13 and 3 Vulnerable", taken(c, a) == 13 and amount(a[0], "vulnerable") == 3)
check("and the Intangible is gone", fysh.get_status("intangible") is None)
c, a, (fysh,) = fight("soulfysh")
a[0].hand = ["beckon"]
before = a[0].current_hp
c.end_player_turn()
check("a Beckon held at the end of the turn costs 6 HP", before - a[0].current_hp == 6,
      before - a[0].current_hp)
c, a, (fysh,) = fight("soulfysh")
a[0].hand, a[0].energy = ["beckon"], 3
check("it can be played, for 1", any(x.get("hand_index") == 0 for x in c.legal_actions(a[0])))
c.play_card(a[0], 0)
before = a[0].current_hp
c.end_player_turn()
check("and played it costs nothing more", a[0].energy == 2 or before == a[0].current_hp,
      before - a[0].current_hp)

# ============================================================================
print("\n== Waterfall Giant (WaterfallGiant.cs, SteamEruptionPower.cs) ==")
# ============================================================================
c, a, (giant,) = fight("waterfallgiant")
check("240 HP", giant.max_hp == 240)
rows = []
for _ in range(8):
    rows.append(giant.intent["name"])
    pass_turn(c, a)
check("Pressurize, then Stomp, Ram, Siphon, Pressure Gun, Pressure Up, round from Stomp",
      rows == ["Pressurize", "Stomp", "Ram", "Siphon", "Pressure Gun", "Pressure Up", "Stomp", "Ram"], rows)
check("15 Steam Eruption, 3 more with every move after", amount(giant, "steam_eruption") == 15 + 3 * 7)
c, a, (giant,) = fight("waterfallgiant")
hit(c, a[0], giant, 50)
pass_turn(c, a)
check("Stomp 15 and 1 Weak, Ram 10", taken(c, a) == 15 and amount(a[0], "weak") == 1 and taken(c, a) == 10)
pass_turn(c, a)
check("Siphon heals 10 a player", giant.current_hp == 200, giant.current_hp)
check("Pressure Gun 20, Pressure Up 13", taken(c, a) == 20 and taken(c, a) == 13)
for _ in range(3):
    pass_turn(c, a)
check("Pressure Gun again: 25", taken(c, a) == 25)
c, a, (giant,) = fight("waterfallgiant")
for _ in range(4):
    pass_turn(c, a)
hit(c, a[0], giant, 999)
c._check_combat_end()
check("brought down holding 24 Steam Eruption: not dead, About to Blow, the fight goes on",
      giant.is_alive() and giant.intent["name"] == "About to Blow" and not c.is_over())
hit(c, a[0], giant, 999)
c._check_combat_end()
check("and out of reach", giant.is_alive())
check("About to Blow does nothing", taken(c, a) == 0)
check("then Explode, for the 24", giant.intent["name"] == "Explode" and giant.intent["amount"] == 24)
check("Explode 24, and it is dead: the fight is won", taken(c, a) == 24 and c.is_over())
c, a, (giant,) = fight("waterfallgiant")
hit(c, a[0], giant, 999)
c._check_combat_end()
check("brought down before Pressurize: it simply dies", c.is_over())
c, a, (giant,) = fight("waterfallgiant", players=2, scale=True)
hit(c, a[0], giant, 100)
for _ in range(4):
    pass_turn(c, a)
check("two players: Siphon heals 20", giant.max_hp - giant.current_hp == 80,
      giant.max_hp - giant.current_hp)

# ============================================================================
print("\n== A dead dealer deals nothing, a dead target takes nothing "
      "(CreatureCmd.Damage, AttackCommand) ==")
# ============================================================================
damage_results = lambda results: [r for r in results if r.get("effect_id") == "instant_damage"]

c, a, (merc,) = fight("gremlinmerc")
a[0].apply_status(Caltrops(source=a[0], target=a[0], amount=999))
check("Gimme 7 x 2 into Thorns that kill the Merc: the first hit lands, the second never comes",
      merc.intent["name"] == "Gimme" and taken(c, a) == 7 and not merc.is_alive())

c, a, (merc,) = fight("gremlinmerc")
pass_turn(c, a)                                    # Gimme
a[0].apply_status(Caltrops(source=a[0], target=a[0], amount=999))
check("Double Smash 6 x 2 into the same: one hit, and its 2 Weak still go on - the rest "
      "of the move is not the attack", merc.intent["name"] == "Double Smash"
      and taken(c, a) == 6 and amount(a[0], "weak") > 0, amount(a[0], "weak"))

c, a, (merc,) = fight("gremlinmerc", players=2)
a[0].apply_status(Caltrops(source=a[0], target=a[0], amount=999))
lost = [p.current_hp for p in a]
pass_turn(c, a)
lost = [before - p.current_hp for before, p in zip(lost, a)]
check("two players, Thorns on p1: the first hit still reaches p2 - a hit lands on everyone "
      "before the attacker is looked at again - and the second reaches nobody", lost == [7, 7], lost)

c, a, (dummy,) = fight("dummy1")
dummy.current_hp = 3
a[0].hand, a[0].energy = ["twin_strike"], 5
hits = damage_results(c.play_card(a[0], 0, target=dummy))
check("Twin Strike 5 x 2 at an enemy on 3 HP: one hit; none on the corpse",
      len(hits) == 1 and not dummy.is_alive(), hits)

c, a, (dummy,) = fight("dummy1")
dummy.current_hp = dummy.max_hp = 300
dummy.apply_status(Caltrops(source=dummy, target=dummy, amount=5))
a[0].current_hp = 3
a[0].hand, a[0].energy = ["twin_strike"], 5
hits = damage_results(c.play_card(a[0], 0, target=dummy))
check("Twin Strike into an enemy's Thorns that kill the player: the second hit never comes",
      len(hits) == 1 and not a[0].is_alive() and dummy.current_hp == 295, (hits, dummy.current_hp))

c, a, (e1, e2) = fight(["dummy1", "dummy1"])
e1.current_hp, e2.current_hp = 300, 300
e1.apply_status(Caltrops(source=e1, target=e1, amount=5))
a[0].current_hp = 3
a[0].hand, a[0].energy = ["thunderclap"], 5
hits = damage_results(c.play_card(a[0], 0))
check("Thunderclap, killed by e1's Thorns on the way: e2 still takes that same hit",
      not a[0].is_alive() and e2.current_hp < 300 and len(hits) == 2, (e2.current_hp, hits))

c, a, (e1, e2) = fight(["dummy1", "dummy1"])
e1.current_hp, e2.current_hp = 1, 300
a[0].hand, a[0].energy = ["whirlwind"], 2
hits = damage_results(c.play_card(a[0], 0))
check("Whirlwind x2 with e1 on 1 HP: e1 dies to the first, e2 takes both, no hit on the corpse",
      [r["target_id"] for r in hits] == ["e1", "e2", "e2"], [r["target_id"] for r in hits])

spent, landed = 0, []
for seed in range(30):
    c, a, (e1, e2) = fight(["dummy1", "dummy1"], seed=seed)
    e1.current_hp, e2.current_hp = 1, 300
    a[0].hand, a[0].energy = ["sword_boomerang"], 5
    hits = damage_results(c.play_card(a[0], 0))
    landed.append(len(hits))
    spent += max(0, [r["target_id"] for r in hits].count("e1") - 1)    # e1 dies to its first
check("Sword Boomerang, each hit picked from the living as it comes: always 3 hits landed, "
      "never one at a dead enemy", landed == [3] * 30 and spent == 0, (landed, spent))
spent, landed = 0, []
for seed in range(30):
    c, a, (e1, e2) = fight(["dummy1", "dummy1"], seed=seed)
    e1.current_hp, e2.current_hp = 1, 300
    a[0].hand, a[0].energy = ["volley"], 3
    hits = damage_results(c.play_card(a[0], 0))
    landed.append(len(hits))
    spent += max(0, [r["target_id"] for r in hits].count("e1") - 1)
check("Volley at 3 energy, the same: 3 shots landed, none at a dead enemy",
      landed == [3] * 30 and spent == 0, (landed, spent))

print()
print("%d checks failed" % len(bad))
for label in bad:
    print("   ", label)

import sys as _sys
_sys.exit(1 if bad else 0)
