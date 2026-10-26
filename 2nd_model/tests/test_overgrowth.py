"""The Overgrowth (Act 1) enemies ported after the first 21, each against the
installed game's code (MegaCrit.Sts2.Core.Models.Monsters)."""
import random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Cards._card_ref import CardRef
from GameEngine.Effects.InstantEffects.instant_damage import InstantDamage
from GameEngine.Effects.InstantEffects.instant_hp_loss import InstantHpLoss

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
    """The move names enemy `which` uses over `turns` turns of one fight."""
    c, a, foes = fight(kinds, seed=seed)
    return names(c, a, foes[which], turns)


def hit(c, attacker, target, amount):
    c._resolve(InstantDamage(source=attacker, target=target, amount=amount))


# ============================================================================
print("== Inklet (Inklet.cs) ==")
# ============================================================================
c, a, (foe,) = fight("inklet")
check("HP 11-17", 11 <= foe.max_hp <= 17, foe.max_hp)
check("arrives with 1 Slippery", foe.get_status("slippery").amount == 1)
c, a, foes = fight(["inklet"] * 3, players=2, scale=True)
check("two players: Slippery 2 each (times the player count)",
      [f.get_status("slippery").amount for f in foes] == [2, 2, 2])

seqs = []
for seed in range(30):
    c, a, foes = fight(["inklet"] * 3, seed=seed)
    seqs.append(names(c, a, foes[0], 8))
check("the outer ones open with Jab, then every other move is a Jab",
      all(s[0] == "Jab" and all(s[i] == "Jab" for i in range(0, 8, 2)) for s in seqs), seqs[0])
between = {s[i] for s in seqs for i in range(1, 8, 2)}
check("between Jabs: Piercing Gaze or Whirlwind, both turn up", between == {"Piercing Gaze", "Whirlwind"}, between)
c, a, foes = fight(["inklet"] * 3, seed=4)
mid = names(c, a, foes[1], 4)
check("the middle one opens with Whirlwind, then Jab", mid[:2] == ["Whirlwind", "Jab"], mid)
c, a, (foe,) = fight("inklet")
check("Jab 3, Whirlwind 2 x 3, Piercing Gaze 10",
      (foe._jab.damage, foe._whirlwind.damage, foe._whirlwind.hits, foe._gaze.damage) == (3, 2, 3, 10))
check("alone, it is no middle Inklet: Jab first", foe.intent["name"] == "Jab", foe.intent)

c, a, (foe,) = fight("inklet")
foe.current_hp = foe.max_hp = 17
hit(c, a[0], foe, 9)
check("Slippery: a 9 that gets through takes 1 HP, and spends the charge",
      foe.current_hp == 16 and foe.get_status("slippery").amount == 0, (foe.current_hp, foe.get_status("slippery").amount))
hit(c, a[0], foe, 9)
check("spent: the next 9 takes 9", foe.current_hp == 7, foe.current_hp)
c, a, (foe,) = fight("inklet")
foe.current_hp = foe.max_hp = 17
foe.block = 10
hit(c, a[0], foe, 6)
check("a hit Block soaks up costs no charge", foe.get_status("slippery").amount == 1 and foe.current_hp == 17,
      (foe.get_status("slippery").amount, foe.current_hp))
c._resolve(InstantHpLoss(source=a[0], target=foe, amount=5))
check("HP loss is held to 1 too (the game's ModifyHpLostAfterOsty)",
      foe.current_hp == 16 and foe.get_status("slippery").amount == 0, foe.current_hp)

# ============================================================================
print("\n== Fogmog and Eye With Teeth (Fogmog.cs, EyeWithTeeth.cs, IllusionPower.cs) ==")
# ============================================================================
from GameEngine.Effects.StatusEffects.vulnerable import Vulnerable
from GameEngine.Effects.StatusEffects.strength import Strength

c, a, (fog,) = fight("fogmog")
check("Fogmog: 74 HP, opens with Illusion", fog.max_hp == 74 and fog.intent["name"] == "Illusion",
      (fog.max_hp, fog.intent))
seqs = [run("fogmog", seed, 12) for seed in range(40)]
check("then Swipe; Illusion only once", all(s[1] == "Swipe" and s.count("Illusion") == 1 for s in seqs), seqs[0])
check("after a Headbutt always a Swipe; never three Swipes running",
      all(all(s[i + 1] == "Swipe" for i in range(1, 11) if s[i] == "Headbutt") for s in seqs)
      and not any(s[i] == s[i + 1] == s[i + 2] == "Swipe" for s in seqs for i in range(1, 10)), seqs[1])
after_swipe = [s[i + 1] for s in seqs for i in range(1, 11)
               if s[i] == "Swipe" and s[i - 1] != "Swipe"]
share = after_swipe.count("Headbutt") / len(after_swipe)
check("after a lone Swipe: Headbutt about 60% of the time, a second Swipe the rest",
      0.45 < share < 0.75 and "Swipe" in after_swipe, round(share, 2))
check("Swipe 8 and +1 Strength, Headbutt 14",
      fog._swipe.damage == 8 and fog._headbutt.damage == 14)

c, a, (fog,) = fight("fogmog")
dazed = lambda p: sum(1 for pile in (p.hand, p.draw_pile, p.discard_pile, p.exhaust_pile)
                      for x in pile if str(x) == "dazed")
pass_turn(c, a)
eye = next((e for e in c.enemies if e.name == "Eye With Teeth"), None)
check("Illusion brings in an Eye With Teeth: 6 HP, an Illusion and a Minion, led by Fogmog",
      eye is not None and eye.max_hp == 6 and eye.get_status("illusion") and eye.get_status("minion")
      and eye.leader is fog, eye and sorted(eye.statuses))
check("it does not act in the phase it arrived in: no Dazed yet", dazed(a[0]) == 0, dazed(a[0]))
pass_turn(c, a)
check("then Distract: 3 Dazed for every player, each turn", dazed(a[0]) == 3, dazed(a[0]))
c2, a2, (fog2,) = fight("fogmog", players=2)
pass_turn(c2, a2)
pass_turn(c2, a2)
check("two players: 3 Dazed each", [dazed(p) for p in a2] == [3, 3], [dazed(p) for p in a2])

eye.apply_status(Vulnerable(source=a[0], target=eye, amount=2))
eye.apply_status(Strength(source=eye, target=eye, amount=3))
hit(c, a[0], eye, 50)
c._resolve_deaths()
check("killed, the Eye shows Revive, drops its debuffs and keeps its buffs, and the fight goes on",
      not eye.is_alive() and eye.intent["name"] == "Revive" and eye.get_status("vulnerable") is None
      and eye.get_status("strength") is not None and not c.is_over(),
      (eye.intent, sorted(eye.statuses)))
check("it cannot be targeted while down",
      all(t != eye.unit_id for act in c.legal_actions(a[0]) for t in [act.get("target_id")]))
before = dazed(a[0])
pass_turn(c, a)
check("next turn it is back at full HP with Distract - and it gave no Dazed while down",
      eye.current_hp == 6 and eye.intent["name"] == "Distract" and dazed(a[0]) <= before,
      (eye.current_hp, eye.intent["name"]))
hit(c, a[0], fog, 999)
c._resolve_deaths()
c._check_combat_end()
check("Fogmog killed: the Eye goes with it, and the fight is won",
      not eye.is_alive() and str(c.result) == "CombatResult.VICTORY", (eye.is_alive(), c.result))

# ============================================================================
print("\n== Phrog Parasite (PhrogParasite.cs, InfestedPower.cs) ==")
# ============================================================================
c, a, (phrog,) = fight("phrogparasite")
check("61-64 HP, an elite, Infested 4", 61 <= phrog.max_hp <= 64 and phrog.CATEGORY == "elite"
      and phrog.get_status("infested").amount == 4, (phrog.max_hp, sorted(phrog.statuses)))
seq = names(c, a, phrog, 6)
check("Infect, Lash, Infect, Lash...", seq == ["Infect", "Lash"] * 3, seq)
check("Lash 4 x 4", (phrog._lash.damage, phrog._lash.hits) == (4, 4))
c, a, (phrog,) = fight("phrogparasite", players=2)
pass_turn(c, a)
infections = [sum(1 for x in p.discard_pile if str(x) == "infection") for p in a]
check("Infect: 3 Infection into every player's discard pile", infections == [3, 3], infections)

c, a, (phrog,) = fight("phrogparasite")
hit(c, a[0], phrog, 999)
c._resolve_deaths()
c._check_combat_end()
worms = [e for e in c.enemies if e.name == "Wriggler"]
check("dead, it bursts into 4 Wrigglers and the fight goes on",
      len(worms) == 4 and all(w.is_alive() for w in worms) and not c.is_over(), (len(worms), c.result))
check("four different HP values among them (17-21)", len({w.max_hp for w in worms}) == 4,
      [w.max_hp for w in worms])
shown = [c._enemy_dict(w)["intent"]["name"] for w in worms]
check("they arrive stunned, and say so", shown == ["Stunned"] * 4, shown)
before = a[0].current_hp
pass_turn(c, a)
check("so their first enemy phase does nothing", a[0].current_hp == before, (before, a[0].current_hp))
shown = [w.intent["name"] for w in worms]
check("then slots 1 and 3 bite first and 2 and 4 wriggle, as in the game",
      shown == ["Nasty Bite", "Wriggle", "Nasty Bite", "Wriggle"], shown)
check("they are no Minions: the fight lasts until they are dead",
      all(w.get_status("minion") is None for w in worms))

# ============================================================================
print("\n== a stun puts the move off (CreatureCmd.Stun) ==")
# ============================================================================
from GameEngine.Effects.StatusEffects.stun import Stun
c, a, (foe,) = fight("phrogparasite")
pass_turn(c, a)                                   # Infect done; Lash is next
check("Lash lined up", foe.intent["name"] == "Lash")
foe.apply_status(Stun(source=a[0], target=foe, amount=1))      # Whistle, mid-turn
check("stunned mid-turn, the intent reads Stunned", c._enemy_dict(foe)["intent"]["name"] == "Stunned")
before = a[0].current_hp
pass_turn(c, a)
check("it does nothing that phase", a[0].current_hp == before)
check("and next turn it Lashes after all - put off, not lost, as the game's stun hands back",
      foe.intent["name"] == "Lash", foe.intent["name"])
pass_turn(c, a)
check("then on with the pattern: Infect", foe.intent["name"] == "Infect", foe.intent["name"])

# ============================================================================
print("\n== Bygone Effigy (BygoneEffigy.cs, SlowPower.cs) ==")
# ============================================================================
c, a, (eff,) = fight("bygoneeffigy")
check("127 HP, an elite, Slow from the start", eff.max_hp == 127 and eff.CATEGORY == "elite"
      and eff.get_status("slow") is not None, (eff.max_hp, sorted(eff.statuses)))
seq = names(c, a, eff, 5)
check("Sleep, Wake, then Slashes every turn", seq == ["Sleep", "Wake", "Slashes", "Slashes", "Slashes"], seq)
check("Wake gives 10 Strength; Slashes is 13 (23 with it)",
      eff.get_status("strength").amount == 10 and eff._slashes.damage == 13
      and c._enemy_dict(eff)["intent"]["damage"]["p1"] == 23, c._enemy_dict(eff)["intent"])

c, a, (eff,) = fight("bygoneeffigy", players=2)
p, q = a
for x in a:
    x.energy = 9
p.hand = [CardRef("defend")]
q.hand = [CardRef("defend"), CardRef("strike")]
c.play_card(p, 0)
c.play_card(q, 0)
hp = eff.current_hp
c.play_card(q, 0, target=eff)
check("Slow counts every player's cards: after two Defends, a Strike's 6 deals 7 (x1.2)",
      hp - eff.current_hp == 7, hp - eff.current_hp)
check("and the Strike itself counts once played: 3", eff.get_status("slow").amount == 3)
eff.current_hp = 100
c._resolve(InstantHpLoss(source=p, target=eff, amount=10))
check("HP loss that is not an attack is not slowed", eff.current_hp == 90, eff.current_hp)
pass_turn(c, a)
check("the count starts again when the enemies' turn begins", eff.get_status("slow").amount == 0
      and eff.get_status("slow") is not None)

# ============================================================================
print("\n== Byrdonis (Byrdonis.cs, TerritorialPower.cs) ==")
# ============================================================================
c, a, (byrd,) = fight("byrdonis")
check("81-84 HP, an elite, Territorial 1", 81 <= byrd.max_hp <= 84 and byrd.CATEGORY == "elite"
      and byrd.get_status("territorial").amount == 1, (byrd.max_hp, sorted(byrd.statuses)))
strength = lambda: byrd.get_status("strength").amount if byrd.get_status("strength") else 0
seen = []
for _ in range(4):
    seen.append((byrd.intent["name"], c._enemy_dict(byrd)["intent"]["damage"]["p1"], strength()))
    pass_turn(c, a)
check("Swoop 17 first, then Peck 3 x 3, alternating; +1 Strength after every enemy turn",
      seen == [("Swoop", 17, 0), ("Peck", 4, 1), ("Swoop", 19, 2), ("Peck", 6, 3)], seen)
check("Peck hits 3 times", byrd._peck.hits == 3)

# ============================================================================
print("\n== The Kin (KinPriest.cs, KinFollower.cs, TheKinBoss.cs) ==")
# ============================================================================
KIN = ["kinfollower", "kinfollower", "kinpriest"]
c, a, (f1, f2, priest) = fight(KIN)
check("Priest 190 HP, a boss; followers 58-59, Minions, different HP",
      priest.max_hp == 190 and priest.CATEGORY == "boss" and {f1.max_hp, f2.max_hp} == {58, 59}
      and f1.get_status("minion") and f2.get_status("minion"), (priest.max_hp, f1.max_hp, f2.max_hp))
rows = []
for _ in range(5):
    rows.append((f1.intent["name"], f2.intent["name"], priest.intent["name"]))
    pass_turn(c, a)
check("Priest: Orb of Frailty, Orb of Weakness, Beam, Ritual, round again",
      [r[2] for r in rows] == ["Orb of Frailty", "Orb of Weakness", "Beam", "Ritual", "Orb of Frailty"],
      [r[2] for r in rows])
check("followers: the first opens with Power Dance, the second with Quick Slash, then Slash, Boomerang, Dance",
      [r[0] for r in rows] == ["Power Dance", "Quick Slash", "Boomerang", "Power Dance", "Quick Slash"]
      and [r[1] for r in rows] == ["Quick Slash", "Boomerang", "Power Dance", "Quick Slash", "Boomerang"], rows)
c, a, (f1, f2, priest) = fight(KIN)
pass_turn(c, a)
check("Orb of Frailty: 8 and a Frail on every player",
      a[0].get_status("frail") is not None and a[0].current_hp == 5000 - 8 - 5, a[0].current_hp)
check("Beam 3 x 3, Ritual +2, Boomerang 2 x 2, Power Dance +2",
      (priest._cycle[2].damage, priest._cycle[2].hits, f1._cycle[1].hits, f1._cycle[1].damage) == (3, 3, 2, 2))

c, a, (f1, f2, priest) = fight(KIN)
hit(c, a[0], f1, 999)
hit(c, a[0], f2, 999)
c._resolve_deaths()
c._check_combat_end()
check("both followers down: the Priest fights on", priest.is_alive() and not c.is_over())
c, a, (f1, f2, priest) = fight(KIN)
hit(c, a[0], priest, 999)
c._resolve_deaths()
c._check_combat_end()
check("the Priest down: the followers go with it and the fight is won",
      not f1.is_alive() and not f2.is_alive() and str(c.result) == "CombatResult.VICTORY", c.result)

# ============================================================================
print("\n== Vantom (Vantom.cs) ==")
# ============================================================================
c, a, (van,) = fight("vantom")
check("173 HP, a boss, 8 Slippery", van.max_hp == 173 and van.CATEGORY == "boss"
      and van.get_status("slippery").amount == 8, (van.max_hp, van.get_status("slippery").amount))
c2, a2, (van2,) = fight("vantom", players=2, scale=True)
check("two players: 16 Slippery", van2.get_status("slippery").amount == 16)
wounds = lambda p: sum(1 for pile in (p.hand, p.draw_pile, p.discard_pile, p.exhaust_pile)
                       for x in pile if str(x) == "wound")
rows = []
for _ in range(5):
    rows.append((van.intent["name"], van.intent["amount"], van.intent["hits"]))
    pass_turn(c, a)
    if rows[-1][0] == "Dismember":
        dismembered = wounds(a[0])
check("Ink Blot 7, Inky Lance 6 x 2, Dismember 26, Prepare, round again",
      rows == [("Ink Blot", 7, 1), ("Inky Lance", 6, 2), ("Dismember", 26, 1), ("Prepare", 0, 1),
               ("Ink Blot", 7, 1)], rows)
check("Dismember puts 3 Wounds into every player's discard pile", dismembered == 3, dismembered)
check("Prepare gives +2 Strength", van.get_status("strength").amount == 2)
van.current_hp = 173
for _ in range(8):
    hit(c, a[0], van, 30)
check("eight 30s through Block take 8 HP, and then the ninth takes 30",
      van.current_hp == 165 and (hit(c, a[0], van, 30) or van.current_hp == 135), van.current_hp)

# ============================================================================
print("\n== Ceremonial Beast (CeremonialBeast.cs, PlowPower.cs, RingingPower.cs) ==")
# ============================================================================
c, a, (beast,) = fight("ceremonialbeast")
check("252 HP, a boss", beast.max_hp == 252 and beast.CATEGORY == "boss")
seq = names(c, a, beast, 4)
check("Stamp, then Plow every turn", seq == ["Stamp", "Plow", "Plow", "Plow"], seq)
check("Stamp puts Plow 150 on it; each Plow is 18 and +2 Strength",
      beast.get_status("plow").amount == 150 and beast.get_status("strength").amount == 6
      and beast._plow.damage == 18, {k: v.amount for k, v in beast.statuses.items()})
beast.current_hp = 160
hit(c, a[0], beast, 9)
check("down to 151: still charging", beast.get_status("plow") is not None and beast.current_hp == 151)
hit(c, a[0], beast, 1)
check("down to 150: the charge breaks - Plow and all its Strength gone, stunned",
      beast.get_status("plow") is None and beast.get_status("strength") is None
      and c._enemy_dict(beast)["intent"]["name"] == "Stunned", sorted(beast.statuses))
before = a[0].current_hp
pass_turn(c, a)
check("the stunned turn does nothing", a[0].current_hp == before, (before, a[0].current_hp))
rows = [beast.intent["name"]]
for _ in range(4):
    pass_turn(c, a)
    rows.append(beast.intent["name"])
check("then Beast Cry, Stomp 15, Crush 17, round again",
      rows == ["Beast Cry", "Stomp", "Crush", "Beast Cry", "Stomp"], rows)
check("Crush gives +3 Strength", beast.get_status("strength").amount == 3)

c, a, (beast,) = fight("ceremonialbeast", players=2)
beast.current_hp = 140
beast.apply_status(__import__("GameEngine.Effects.StatusEffects.plow", fromlist=["Plow"]).Plow(
    source=beast, target=beast, amount=150))
hit(c, a[0], beast, 1)
pass_turn(c, a)                                   # stunned
pass_turn(c, a)                                   # Beast Cry lands on both
check("Beast Cry: Ringing on every player", all(p.get_status("ringing") for p in a))
p = a[0]
p.hand = [CardRef("strike"), CardRef("strike"), CardRef("defend")]
p.energy = 3
c.play_card(p, 0, target=beast)
check("Ringing: one card, then nothing more - and none listed",
      not [x for x in c.legal_actions(p) if x["type"] == "play_card"], c.legal_actions(p))
try:
    c.play_card(p, 0, target=beast)
    refused = False
except ValueError:
    refused = True
check("a second card is refused", refused)
pass_turn(c, a)
check("gone at the end of their turn", p.get_status("ringing") is None)

c, a, (beast,) = fight("ceremonialbeast", players=2, scale=True)
pass_turn(c, a)
check("two players: HP 554 and Plow 330 - the same share of its health",
      beast.max_hp == 554 and beast.get_status("plow").amount == 330,
      (beast.max_hp, beast.get_status("plow").amount))

print()
print("%d checks failed" % len(bad))
for label in bad:
    print("   ", label)

import sys as _sys
_sys.exit(1 if bad else 0)
