"""Batch 12: play interception."""
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
    for e in enemies:
        e.choose_intent = lambda context=None, e=e: setattr(
            e, "intent", {"type": "attack", "amount": 1})
        e.choose_intent()

check("registry has 223 cards", len(known_card_ids()) == 223, len(known_card_ids()))

# --- Havoc -----------------------------------------------------------------
c, a, es = fight(seed=2)
a[0].draw_pile = ["defend", "strike"]        # strike is on top
play(c, a[0], "havoc")
check("Havoc plays the top card of the draw pile", es[0].current_hp == 194,
      es[0].current_hp)
check("Havoc exhausts what it played", a[0].exhaust_pile == ["strike"],
      a[0].exhaust_pile)
check("Havoc took it out of the draw pile", a[0].draw_pile == ["defend"],
      a[0].draw_pile)
check("Havoc itself goes to the discard", a[0].discard_pile == ["havoc"],
      a[0].discard_pile)

c, a, es = fight(seed=2)
a[0].draw_pile = []
play(c, a[0], "havoc")
check("Havoc with an empty draw pile is a no-op", a[0].exhaust_pile == [],
      a[0].exhaust_pile)

c, a, es = fight(seed=2)
a[0].draw_pile = ["burn"]                    # unplayable
play(c, a[0], "havoc")
check("Havoc exhausts an unplayable card without resolving it",
      a[0].exhaust_pile == ["burn"] and a[0].current_hp == a[0].max_hp,
      (a[0].exhaust_pile, a[0].current_hp))

c, a, es = fight(seed=2)
a[0].draw_pile = ["strike"]
es[0].current_hp = 0                         # nothing alive to hit
play(c, a[0], "havoc")
check("Havoc still exhausts when there is nothing to hit",
      a[0].exhaust_pile == ["strike"], a[0].exhaust_pile)

# --- auto-target picks the weakest enemy -----------------------------------
c, a, es = fight(n_enemies=3, seed=3)
es[0].current_hp = 100
es[1].current_hp = 20
es[2].current_hp = 60
a[0].draw_pile = ["strike"]
play(c, a[0], "havoc")
check("an auto-played attack takes the weakest enemy",
      [e.current_hp for e in es] == [100, 14, 60], [e.current_hp for e in es])

# --- Beat Down / Catastrophe -----------------------------------------------
c, a, es = fight(seed=4)
a[0].discard_pile = ["strike", "strike", "strike", "defend"]
play(c, a[0], "beat_down")
check("Beat Down plays 3 Attacks from the discard", es[0].current_hp == 182,
      es[0].current_hp)
check("Beat Down leaves the non-Attack alone", "defend" in a[0].discard_pile,
      a[0].discard_pile)
check("the played Attacks come back to the discard",
      a[0].discard_pile.count("strike") == 3, a[0].discard_pile)

c, a, es = fight(seed=4)
a[0].discard_pile = ["strike"]
play(c, a[0], "beat_down")
check("Beat Down copes with fewer than 3 Attacks", es[0].current_hp == 194,
      es[0].current_hp)

c, a, es = fight(seed=4)
a[0].discard_pile = ["defend"]
play(c, a[0], "beat_down")
check("Beat Down with no Attacks is a no-op", es[0].current_hp == 200,
      es[0].current_hp)

c, a, es = fight(seed=5)
a[0].draw_pile = ["strike", "strike"]
play(c, a[0], "catastrophe")
check("Catastrophe plays 2 cards from the draw pile", es[0].current_hp == 188,
      es[0].current_hp)
check("Catastrophe empties them out of the draw pile", a[0].draw_pile == [],
      a[0].draw_pile)

# --- Mayhem ----------------------------------------------------------------
c, a, es = fight(seed=6)
play(c, a[0], "mayhem")
check("Mayhem does nothing on the turn it lands", es[0].current_hp == 200,
      es[0].current_hp)
# The turn-start hand comes off this pile first, so stock it deep enough that
# a known card is still on top when TURN_START fires.
a[0].draw_pile = ["strike"] + ["defend"] * Combat.HAND_SIZE
hp = es[0].current_hp
c.end_player_turn()
check("Mayhem plays the top card at turn start", es[0].current_hp == hp - 6,
      es[0].current_hp)
check("Mayhem took it out of the draw pile", "strike" not in a[0].draw_pile,
      a[0].draw_pile)

c, a, es = fight(seed=6)
play(c, a[0], "mayhem")
a[0].draw_pile = []
a[0].discard_pile = []
c.end_player_turn()
check("Mayhem with nothing to play is quiet", es[0].current_hp == 200,
      es[0].current_hp)

# --- Stampede --------------------------------------------------------------
c, a, es = fight(seed=7)
play(c, a[0], "stampede")
a[0].hand = ["strike", "defend"]
hp = es[0].current_hp
c.end_player_turn()
check("Stampede plays an Attack from hand at end of turn",
      es[0].current_hp == hp - 6, es[0].current_hp)

c, a, es = fight(seed=7)
play(c, a[0], "stampede")
a[0].hand = ["defend"]
hp = es[0].current_hp
c.end_player_turn()
check("Stampede with no Attack in hand is quiet", es[0].current_hp == hp,
      es[0].current_hp)

# --- One-Two Punch ---------------------------------------------------------
c, a, es = fight(seed=8)
play(c, a[0], "one_two_punch")
check("One-Two Punch grants one extra play", a[0].extra_attack_plays == 1)
play(c, a[0], "strike", es[0])
check("the next Attack is played twice", es[0].current_hp == 188,
      es[0].current_hp)
check("the grant is spent", a[0].extra_attack_plays == 0)
check("a replayed card still reaches the discard once",
      a[0].discard_pile.count("strike") == 1, a[0].discard_pile)
play(c, a[0], "strike", es[0])
check("the Attack after that is played once", es[0].current_hp == 182,
      es[0].current_hp)

c, a, es = fight(seed=8)
play(c, a[0], "one_two_punch")
play(c, a[0], "defend")
check("One-Two Punch is not spent by a Skill", a[0].extra_attack_plays == 1)
check("and the Skill is not doubled", a[0].block == 5, a[0].block)

c, a, es = fight(seed=8)
play(c, a[0], "one_two_punch")
c.end_player_turn()
check("One-Two Punch expires at end of turn", a[0].extra_attack_plays == 0)

# --- Tag Team --------------------------------------------------------------
c, a, es = fight(n_allies=2, seed=9)
play(c, a[0], "tag_team", es[0])
check("Tag Team deals 11", es[0].current_hp == 189, es[0].current_hp)
check("Tag Team marks the enemy", es[0].get_status("tag_team").amount == 1)
play(c, a[0], "strike", es[0])
check("the applier gets nothing from it", es[0].current_hp == 183,
      es[0].current_hp)
play(c, a[1], "strike", es[0])
check("another player's Attack is played twice", es[0].current_hp == 171,
      es[0].current_hp)
check("the mark is spent",
      es[0].get_status("tag_team") is None
      or es[0].get_status("tag_team").amount == 0)

# --- Hellraiser ------------------------------------------------------------
c, a, es = fight(seed=10)
play(c, a[0], "hellraiser")
a[0].hand = []
a[0].draw_pile = ["strike", "defend"]
hp = es[0].current_hp
c._resolve(__import__("GameEngine.Effects.InstantEffects.instant_draw",
                      fromlist=["InstantDraw"]).InstantDraw(
    source=a[0], target=a[0], amount=2, rng=c.rng))
check("Hellraiser plays a drawn Strike", es[0].current_hp == hp - 6,
      es[0].current_hp)
check("the Strike left the hand and went to the discard",
      a[0].hand == ["defend"] and "strike" in a[0].discard_pile,
      (a[0].hand, a[0].discard_pile))

c, a, es = fight(seed=10)
play(c, a[0], "hellraiser")
a[0].hand = ["strike"]          # already held, not drawn
a[0].draw_pile = ["defend"]
hp = es[0].current_hp
c._resolve(__import__("GameEngine.Effects.InstantEffects.instant_draw",
                      fromlist=["InstantDraw"]).InstantDraw(
    source=a[0], target=a[0], amount=1, rng=c.rng))
check("Hellraiser ignores Strikes already in hand", es[0].current_hp == hp,
      es[0].current_hp)

# --- Nostalgia -------------------------------------------------------------
c, a, es = fight(seed=11)
play(c, a[0], "nostalgia")
a[0].draw_pile = []
play(c, a[0], "strike", es[0])
check("Nostalgia sends the first Attack to the top of the draw pile",
      a[0].draw_pile == ["strike"] and "strike" not in a[0].discard_pile,
      (a[0].draw_pile, a[0].discard_pile))
play(c, a[0], "defend")
check("only the first card each turn is redirected",
      a[0].discard_pile == ["defend"], a[0].discard_pile)
c.end_player_turn()
a[0].energy = 9
a[0].draw_pile = []
play(c, a[0], "strike", es[0])
check("Nostalgia resets next turn", a[0].draw_pile == ["strike"],
      a[0].draw_pile)

# --- Rebound ---------------------------------------------------------------
c, a, es = fight(seed=12)
a[0].draw_pile = []
play(c, a[0], "rebound", es[0])
check("Rebound deals 9", es[0].current_hp == 191, es[0].current_hp)
check("Rebound does not redirect itself",
      a[0].discard_pile == ["rebound"] and a[0].draw_pile == [],
      (a[0].discard_pile, a[0].draw_pile))
play(c, a[0], "defend")
check("Rebound sends the NEXT card to the top of the draw pile",
      a[0].draw_pile == ["defend"], a[0].draw_pile)
play(c, a[0], "strike", es[0])
check("Rebound is a one-shot", "strike" in a[0].discard_pile, a[0].discard_pile)

# --- Juggling --------------------------------------------------------------
c, a, es = fight(seed=13)
play(c, a[0], "juggling")
for i in range(2):
    a[0].hand = ["strike"]
    c.play_card(a[0], 0, target=es[0])
check("Juggling is quiet for the first two Attacks", a[0].hand == [], a[0].hand)
a[0].hand = ["bludgeon"]
c.play_card(a[0], 0, target=es[0])
check("Juggling copies the third Attack into hand", a[0].hand == ["bludgeon"],
      a[0].hand)
a[0].hand = []
a[0].energy = 9
play(c, a[0], "strike", es[0])
check("Juggling does not fire on the fourth", a[0].hand == [], a[0].hand)

# --- Howl from Beyond ------------------------------------------------------
c, a, es = fight(n_enemies=2, seed=14)
play(c, a[0], "howl_from_beyond")
check("Howl hits all enemies for 18", [e.current_hp for e in es] == [182, 182],
      [e.current_hp for e in es])
c.end_player_turn()
check("Howl does not echo from the discard pile",
      [e.current_hp for e in es] == [182, 182], [e.current_hp for e in es])

c, a, es = fight(n_enemies=2, seed=14)
play(c, a[0], "howl_from_beyond")
a[0].discard_pile.remove("howl_from_beyond")
a[0].exhaust_pile.append("howl_from_beyond")     # as Fiend Fire would
c.end_player_turn()
check("Howl echoes from the exhaust pile at end of turn",
      [e.current_hp for e in es] == [164, 164], [e.current_hp for e in es])

# --- Void ------------------------------------------------------------------
c, a, es = fight(seed=15)
a[0].hand = []
a[0].draw_pile = ["void"]
a[0].energy = 3
c._resolve(__import__("GameEngine.Effects.InstantEffects.instant_draw",
                      fromlist=["InstantDraw"]).InstantDraw(
    source=a[0], target=a[0], amount=1, rng=c.rng))
check("drawing Void costs 1 energy", a[0].energy == 2, a[0].energy)

c, a, es = fight(seed=15)
a[0].hand = ["void", "void"]      # already held
a[0].draw_pile = ["strike"]
a[0].energy = 3
c._resolve(__import__("GameEngine.Effects.InstantEffects.instant_draw",
                      fromlist=["InstantDraw"]).InstantDraw(
    source=a[0], target=a[0], amount=1, rng=c.rng))
check("Voids already in hand do not re-trigger on someone else's draw",
      a[0].energy == 3, a[0].energy)

c, a, es = fight(seed=15)
a[0].hand = []
a[0].draw_pile = ["void", "void"]
a[0].energy = 1
c._resolve(__import__("GameEngine.Effects.InstantEffects.instant_draw",
                      fromlist=["InstantDraw"]).InstantDraw(
    source=a[0], target=a[0], amount=2, rng=c.rng))
check("two Voids drawn cost 2, floored at zero", a[0].energy == 0, a[0].energy)
check("Void is unplayable", not create_card("void").properties.playable)

# --- runaway plays are bounded ---------------------------------------------
c, a, es = fight(seed=16)
a[0].draw_pile = ["havoc", "havoc", "havoc", "havoc", "havoc", "strike"]
play(c, a[0], "havoc")
check("Havoc into Havoc terminates", True, "depth-bounded, no recursion error")
check("and it stopped short of the whole pile",
      len(a[0].exhaust_pile) <= Combat.MAX_PLAY_DEPTH + 1,
      len(a[0].exhaust_pile))

print()
print("ALL BATCH 12 CHECKS PASSED" if not bad else "FAILURES: %d" % len(bad))
for b in bad:
    print("   ", b)

import sys as _sys
_sys.exit(1 if bad else 0)
