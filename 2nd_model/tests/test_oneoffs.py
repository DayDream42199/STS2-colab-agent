"""Batch 11: the six one-off hooks."""
import random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Registry.card_registry import create_card, known_card_ids
from GameEngine.Cards._card_enums import CardType
from GameEngine.Effects.StatusEffects.vulnerable import Vulnerable
from GameEngine.Effects.StatusEffects.weak import Weak
from GameEngine.Effects.StatusEffects.frail import Frail
from GameEngine.Effects.StatusEffects.strength import Strength

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))

def fight(n_allies=1, n_enemies=1, seed=1, enemy_hp=200):
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

def always_attack(enemies):
    """dummy1 cycles attack / block / debuff, so what an enemy does after a
    skipped turn depends on where the cycle got to. Pin it to attack so damage
    across a turn boundary means something."""
    for e in enemies:
        e.choose_intent = lambda context=None, e=e: setattr(
            e, "intent", {"type": "attack", "amount": 1})
        e.choose_intent()

check("registry has 223 cards", len(known_card_ids()) == 223, len(known_card_ids()))

# --- Barricade -------------------------------------------------------------
c, a, es = fight(seed=2)
a[0].block = 20
c.end_player_turn()
check("without Barricade, block is cleared at turn start", a[0].block == 0, a[0].block)

c, a, es = fight(seed=2)
always_attack(es)
play(c, a[0], "barricade")
a[0].block = 20
c.end_player_turn()
check("Barricade keeps block through the turn boundary (20 - 1 taken)",
      a[0].block == 19, a[0].block)
c.end_player_turn()
check("Barricade is permanent: still holding after a second turn",
      a[0].block == 18, a[0].block)
check("and the block is still real - it soaked both hits",
      a[0].current_hp == a[0].max_hp, a[0].current_hp)

c, a, es = fight(seed=2)
play(c, a[0], "barricade")
a[0].block = 5
c._resolve(__import__("GameEngine.Effects.InstantEffects.instant_damage",
                      fromlist=["InstantDamage"]).InstantDamage(
    source=es[0], target=a[0], amount=3))
check("Barricade does not make block invulnerable", a[0].block == 2, a[0].block)

# --- Whistle / Stun --------------------------------------------------------
c, a, es = fight(seed=3)
always_attack(es)
play(c, a[0], "whistle", es[0])
check("Whistle deals 33", es[0].current_hp == 167, es[0].current_hp)
check("Whistle stuns", es[0].get_status("stun").amount == 1)
hp = a[0].current_hp
a[0].block = 0
c.end_player_turn()
check("a stunned enemy does nothing", a[0].current_hp == hp,
      "hp %d -> %d" % (hp, a[0].current_hp))
check("the stun is spent by being skipped",
      es[0].get_status("stun") is None
      or es[0].get_status("stun").amount == 0, es[0].get_status("stun"))
hp = a[0].current_hp
a[0].block = 0
c.end_player_turn()
check("the enemy acts again the turn after", a[0].current_hp < hp,
      "hp %d -> %d" % (hp, a[0].current_hp))

c, a, es = fight(seed=3)
es[0].current_hp = 5
play(c, a[0], "whistle", es[0])
check("Whistle on a lethal hit leaves no stun on the corpse",
      not es[0].is_alive() and es[0].get_status("stun") is None,
      es[0].statuses)

# --- Battle Trance ---------------------------------------------------------
c, a, es = fight(seed=4)
a[0].hand = []
play(c, a[0], "battle_trance")
check("Battle Trance draws 3", len(a[0].hand) == 3, a[0].hand)
check("Battle Trance applies the lockout",
      a[0].get_status("no_more_draw") is not None)
play(c, a[0], "shrug_it_off")
check("no further drawing this turn", len(a[0].hand) == 0, a[0].hand)
c.end_player_turn()
check("the lockout is gone next turn", a[0].get_status("no_more_draw") is None)
a[0].energy = 9
a[0].draw_pile = ["strike"] * 5      # the checks above burned through the deck
a[0].hand = []
play(c, a[0], "shrug_it_off")
check("drawing works again next turn", len(a[0].hand) == 1, a[0].hand)

# --- Pillage ---------------------------------------------------------------
c, a, es = fight(seed=5)
a[0].hand = []
a[0].draw_pile = ["defend", "strike", "strike", "strike"]  # drawn from the end
play(c, a[0], "pillage", es[0])
check("Pillage deals 6", es[0].current_hp == 194, es[0].current_hp)
check("Pillage draws through the Attacks and stops on the non-Attack",
      a[0].hand == ["strike", "strike", "strike", "defend"], a[0].hand)
check("Pillage left the draw pile empty", a[0].draw_pile == [], a[0].draw_pile)

c, a, es = fight(seed=5)
a[0].hand = []
a[0].draw_pile = ["strike", "defend", "strike"]
play(c, a[0], "pillage", es[0])
check("Pillage stops at the first non-Attack",
      a[0].hand == ["strike", "defend"], a[0].hand)

c, a, es = fight(seed=5)
a[0].hand = []
a[0].draw_pile = ["strike", "strike"]
a[0].discard_pile = []
play(c, a[0], "pillage", es[0])
check("Pillage stops when the deck runs out", a[0].hand == ["strike", "strike"],
      a[0].hand)

c, a, es = fight(seed=5)
a[0].hand = []
a[0].draw_pile = ["defend"]
play(c, a[0], "pillage", es[0])
check("Pillage on an immediate non-Attack draws exactly 1",
      a[0].hand == ["defend"], a[0].hand)

c, a, es = fight(seed=6)
a[0].hand = []
a[0].draw_pile = ["strike", "strike", "strike"]
a[0].discard_pile = []
play(c, a[0], "battle_trance")
a[0].energy = 9
# Pillage alongside a marker card, so playing it does not wipe the hand the way
# the play() helper would - what is measured is whether Pillage adds anything.
a[0].hand = ["pillage", "defend"]
a[0].draw_pile = ["strike", "strike", "strike"]
c.play_card(a[0], 0, target=es[0])
check("Battle Trance stops Pillage too", a[0].hand == ["defend"], a[0].hand)
check("and Pillage's damage still lands", es[0].current_hp == 194, es[0].current_hp)

# --- Rend ------------------------------------------------------------------
c, a, es = fight(seed=7)
play(c, a[0], "rend", es[0])
check("Rend with no debuffs deals 10", es[0].current_hp == 190, es[0].current_hp)

c, a, es = fight(seed=7)
es[0].apply_status(Vulnerable(source=a[0], target=es[0], amount=3))
play(c, a[0], "rend", es[0])
check("Rend counts a debuff once regardless of stacks: (10+5)*1.5",
      es[0].current_hp == 178, es[0].current_hp)

c, a, es = fight(seed=7)
es[0].apply_status(Weak(source=a[0], target=es[0], amount=1))
es[0].apply_status(Frail(source=a[0], target=es[0], amount=1))
play(c, a[0], "rend", es[0])
check("Rend counts 2 distinct debuffs: 10 + 10", es[0].current_hp == 180,
      es[0].current_hp)

c, a, es = fight(seed=7)
es[0].apply_status(Strength(source=es[0], target=es[0], amount=5))
play(c, a[0], "rend", es[0])
check("Rend does not count buffs as debuffs", es[0].current_hp == 190,
      es[0].current_hp)

# --- Scrawl ----------------------------------------------------------------
c, a, es = fight(seed=8)
a[0].hand = []
a[0].draw_pile = ["strike"] * 20
play(c, a[0], "scrawl")
check("Scrawl fills the hand to the limit",
      len(a[0].hand) == a[0].HAND_LIMIT, len(a[0].hand))
check("Scrawl exhausts itself", a[0].exhaust_pile == ["scrawl"], a[0].exhaust_pile)

c, a, es = fight(seed=8)
a[0].hand = ["scrawl"] + ["strike"] * 9
a[0].draw_pile = ["strike"] * 20
c.play_card(a[0], 0)
check("Scrawl with 9 already in hand draws 1", len(a[0].hand) == 10,
      len(a[0].hand))

c, a, es = fight(seed=8)
a[0].hand = ["scrawl"] + ["strike"] * 10
a[0].draw_pile = ["strike"] * 20
c.play_card(a[0], 0)
check("Scrawl over the limit is a no-op", len(a[0].hand) == 10, len(a[0].hand))

# --- the hand limit itself -------------------------------------------------
c, a, es = fight(seed=9)
a[0].hand = ["strike"] * 10
a[0].draw_pile = ["strike"] * 20
drawn = a[0].draw(5, c.rng)
check("drawing stops at the hand limit", drawn == [] and len(a[0].hand) == 10,
      (len(drawn), len(a[0].hand)))

print()
print("ALL BATCH 11 CHECKS PASSED" if not bad else "FAILURES: %d" % len(bad))
for b in bad:
    print("   ", b)

import sys as _sys
_sys.exit(1 if bad else 0)
