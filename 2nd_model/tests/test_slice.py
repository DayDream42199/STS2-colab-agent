"""Every card in the slice, against the values in game_engine/cards/pools.py."""
import random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Registry.card_registry import create_card, known_card_ids
from GameEngine.Cards._card_enums import CardType

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print(f"[{'PASS' if c else 'FAIL'}] {l}{(' -> ' + str(d)) if d else ''}")

def fight(n_allies=1, n_enemies=1, seed=1, enemy_hp=200):
    allies = [create_ally("testally1", f"p{i+1}", rng=random.Random(seed)) for i in range(n_allies)]
    enemies = [create_enemy("dummy1", f"e{i+1}", rng=random.Random(seed)) for i in range(n_enemies)]
    c = Combat(allies, enemies, rng=random.Random(seed)); c.start()
    for e in enemies:
        e.current_hp = e.max_hp = enemy_hp
    for a in allies:
        a.energy = 5
    return c, allies, enemies

def play(c, ally, card_id, target=None):
    ally.hand = [card_id]
    return c.play_card(ally, 0, target=target)

check("registry has 223 cards", len(known_card_ids()) == 223, len(known_card_ids()))

# --- Thunderclap: 4 damage + 1 Vulnerable to ALL enemies --------------------
c, a, es = fight(n_enemies=3, seed=2)
play(c, a[0], "thunderclap")
check("Thunderclap hits all 3 for 4", [e.current_hp for e in es] == [196] * 3,
      [e.current_hp for e in es])
check("Thunderclap applies Vulnerable 1 to all",
      all(e.get_status("vulnerable").amount == 1 for e in es))
check("Thunderclap statuses are separate objects",
      es[0].get_status("vulnerable") is not es[1].get_status("vulnerable"))
es[0].get_status("vulnerable").on_owner_turn_end()
check("ticking one enemy's Vulnerable leaves the others",
      [e.get_status("vulnerable").amount for e in es] == [0, 1, 1],
      [e.get_status("vulnerable").amount for e in es])

# --- Breakthrough: lose 1 HP, 9 damage to ALL ------------------------------
c, a, es = fight(n_enemies=2, seed=3)
hp = a[0].current_hp
a[0].block = 50
play(c, a[0], "breakthrough")
check("Breakthrough deals 9 to all", [e.current_hp for e in es] == [191, 191],
      [e.current_hp for e in es])
check("Breakthrough HP loss ignores block", a[0].current_hp == hp - 1 and a[0].block == 50,
      f"hp {hp}->{a[0].current_hp}, block {a[0].block}")

# --- Twin Strike: 5 twice, as two separate hits ----------------------------
c, a, es = fight(seed=4)
r = play(c, a[0], "twin_strike", es[0])
check("Twin Strike deals 5 twice", es[0].current_hp == 190, es[0].current_hp)
check("Twin Strike is two effects, not one", len(r) == 2, len(r))
# two hits vs one big hit: block should soak each separately
c, a, es = fight(seed=5)
es[0].block = 3
play(c, a[0], "twin_strike", es[0])
check("each hit meets block separately", es[0].current_hp == 193,
      f"hp={es[0].current_hp}; hit1 5-3block=2 through, hit2 5 through = 7")

# --- Uppercut: 13 damage, 1 Weak, 1 Vulnerable -----------------------------
c, a, es = fight(seed=6)
play(c, a[0], "uppercut", es[0])
check("Uppercut deals 13", es[0].current_hp == 187, es[0].current_hp)
check("Uppercut applies Weak 1", es[0].get_status("weak").amount == 1)
check("Uppercut applies Vulnerable 1", es[0].get_status("vulnerable").amount == 1)

# --- Weak reduces the weakened unit's own outgoing damage ------------------
c, a, es = fight(n_allies=2, seed=7)
a[0].apply_status(__import__(
    "GameEngine.Effects.StatusEffects.weak", fromlist=["Weak"]
).Weak(source=a[0], target=a[0], amount=2))
play(c, a[0], "twin_strike", es[0])
check("Weak cuts our damage to 0.75x", es[0].current_hp == 194,
      f"hp={es[0].current_hp}; int(5*0.75)=3 per hit, twice = 6")

# --- Inflame: POWER, 2 Strength, leaves play -------------------------------
c, a, es = fight(seed=8)
check("Inflame is a POWER", create_card("inflame").card_type is CardType.POWER)
play(c, a[0], "inflame")
check("Inflame grants 2 Strength", a[0].get_status("strength").amount == 2)
check("Power does not go to discard", "inflame" not in a[0].discard_pile, a[0].discard_pile)
play(c, a[0], "twin_strike", es[0])
check("Strength adds flat per hit", es[0].current_hp == 186,
      f"hp={es[0].current_hp}; (5+2) twice = 14")

# --- Strength is permanent, StrengthThisTurn is not ------------------------
c.end_player_turn()
check("Strength survives the turn", a[0].get_status("strength").amount == 2,
      a[0].to_dict()["statuses"])

# --- Setup Strike: 7 damage, 3 Strength this turn --------------------------
c, a, es = fight(seed=9)
play(c, a[0], "setup_strike", es[0])
check("Setup Strike deals 7", es[0].current_hp == 193, es[0].current_hp)
check("Setup Strike grants 3 Strength this turn",
      a[0].get_status("strength_this_turn").amount == 3)
check("Strength this turn lands on us, not the enemy",
      es[0].get_status("strength_this_turn") is None)
c.end_player_turn()
check("Strength this turn is gone next turn",
      a[0].get_status("strength_this_turn") is None, a[0].to_dict()["statuses"])

# --- ordering: (base + Strength) * Weak, not base * Weak + Strength --------
c, a, es = fight(seed=10)
mods = __import__("GameEngine.Effects.StatusEffects.strength", fromlist=["Strength"])
weakmod = __import__("GameEngine.Effects.StatusEffects.weak", fromlist=["Weak"])
a[0].apply_status(mods.Strength(source=a[0], target=a[0], amount=3))
a[0].apply_status(weakmod.Weak(source=a[0], target=a[0], amount=2))
play(c, a[0], "body_slam", es[0])  # block 0 -> 0 damage; use twin strike instead
c, a, es = fight(seed=10)
a[0].apply_status(mods.Strength(source=a[0], target=a[0], amount=3))
a[0].apply_status(weakmod.Weak(source=a[0], target=a[0], amount=2))
play(c, a[0], "twin_strike", es[0])
check("additive applies before multiplicative", es[0].current_hp == 188,
      f"hp={es[0].current_hp}; (5+3)*0.75=6 twice=12, not (5*0.75)+3=6.75->6 twice")

# --- Pommel Strike: 9 damage, draw 1 ---------------------------------------
c, a, es = fight(seed=11)
a[0].hand = []
before = len(a[0].draw_pile)
r = play(c, a[0], "pommel_strike", es[0])
check("Pommel Strike deals 9", es[0].current_hp == 191, es[0].current_hp)
check("Pommel Strike draws 1", len(a[0].hand) == 1 and len(a[0].draw_pile) == before - 1,
      f"hand={len(a[0].hand)} draw_pile={len(a[0].draw_pile)}")
check("draw is reported on the wire", any(x["effect_id"] == "instant_draw" for x in r), r)

# --- Shrug It Off: 8 block, draw 1 -----------------------------------------
c, a, es = fight(seed=12)
a[0].hand = []
play(c, a[0], "shrug_it_off")
check("Shrug It Off grants 8 block", a[0].block == 8, a[0].block)
check("Shrug It Off draws 1", len(a[0].hand) == 1, len(a[0].hand))

# --- draw reshuffles the discard pile when empty ---------------------------
c, a, es = fight(seed=13)
a[0].discard_pile = list(a[0].draw_pile) + list(a[0].hand)
a[0].draw_pile, a[0].hand = [], []
play(c, a[0], "shrug_it_off")
check("draw reshuffles discard when pile is empty", len(a[0].hand) == 1, len(a[0].hand))

# --- Body Slam: damage equal to your Block ---------------------------------
c, a, es = fight(seed=14)
a[0].block = 17
play(c, a[0], "body_slam", es[0])
check("Body Slam deals damage equal to block", es[0].current_hp == 183, es[0].current_hp)
c, a, es = fight(seed=15)
a[0].block = 0
play(c, a[0], "body_slam", es[0])
check("Body Slam with no block deals nothing", es[0].current_hp == 200, es[0].current_hp)

# --- Coordinate: ALLY-targeted, Strength to the other player ---------------
c, a, es = fight(n_allies=2, seed=16)
play(c, a[0], "coordinate", a[1])
check("Coordinate gives the ally 5 Strength",
      a[1].get_status("strength_this_turn").amount == 5)
check("Coordinate does not buff the caster",
      a[0].get_status("strength_this_turn") is None)
try:
    play(c, a[0], "coordinate", es[0])
    check("Coordinate rejects an enemy target", False, "no exception")
except ValueError as e:
    check("Coordinate rejects an enemy target", "not a valid ally" in str(e), str(e))

print()
print(f"{len(bad)} FAILURE(S): {bad}" if bad else "ALL SLICE CHECKS PASSED")

import sys as _sys
_sys.exit(1 if bad else 0)
