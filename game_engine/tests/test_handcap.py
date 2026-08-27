# -*- coding: utf-8 -*-
"""#46: the 10-card hand limit.

Nothing enforced it before, so Retain could hold an unbounded hand and every
card-generating effect could stack past 10. Source: the wiki's Mechanics
page ("The maximum number of cards allowed in hand is 10. There is no way to
exceed this limit.").
"""
import os
import sys

# The modules under test live one directory up. This used to be a hardcoded
# absolute path, which is why the whole suite only ran on one machine from
# one directory -- and why it lived in a temp folder rather than the repo.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from game_engine.entities import Player, HAND_LIMIT
import game_engine.enemies as E
from game_engine.combat import CombatEngine
import game_engine.cards as C
from game_engine.cards import make_starter_deck, TargetMode
import game_engine.env as ENV

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  [{'ok' if ok else 'FAIL'}] {label}: got {got!r}, want {want!r}")
    if not ok:
        FAILS.append(label)


def bag(hp=4000):
    e = E.make_nibbit()
    e.max_hp = e.hp = hp
    return e


def pool(name):
    for f in (list(C.CARD_POOL_IRONCLAD) + list(C.ANCIENT_CARDS_IRONCLAD)
              + list(C.COLORLESS_POOL) + list(C.ANCIENT_COLORLESS)):
        c = f()
        if c.name == name:
            return c
    raise KeyError(name)


def setup(hp=200):
    p = Player("P", hp, 99, deck=make_starter_deck())
    eng = CombatEngine([p], [bag()], seed=9, scale_enemies=False)
    eng.start_player_turn()
    p.energy = 99
    return eng, p, eng.enemies[0]


def fill(p, n):
    p.hand = [make_starter_deck()[0] for _ in range(n)]


print("=" * 74)
print("The limit itself")
print("=" * 74)
check("HAND_LIMIT is 10", HAND_LIMIT, 10)
check("env.MAX_HAND is the same constant, not a copy", ENV.MAX_HAND, HAND_LIMIT)

eng, p, e = setup()
fill(p, HAND_LIMIT)
p.draw_pile = [make_starter_deck()[1] for _ in range(5)]
n_draw, n_disc = len(p.draw_pile), len(p.discard_pile)
p.draw_cards(3, eng.log)
check("drawing into a full hand does not grow it", len(p.hand), HAND_LIMIT)
check("...the cards still leave the draw pile", len(p.draw_pile), n_draw - 3)
check("...and land in the discard pile", len(p.discard_pile), n_disc + 3)

eng, p, e = setup()
fill(p, 8)
p.draw_pile = [make_starter_deck()[1] for _ in range(5)]
p.draw_cards(5, eng.log)
check("a partial draw fills exactly to the limit", len(p.hand), HAND_LIMIT)
check("...and the overflow is discarded", len(p.discard_pile), 3)

eng, p, e = setup()
fill(p, HAND_LIMIT)
extra = pool("Bludgeon")
landed = p.add_to_hand(extra, eng.log)
check("add_to_hand reports the overflow", landed, False)
check("...the hand is still at the limit", len(p.hand), HAND_LIMIT)
check("...and the card is in the discard pile", extra in p.discard_pile, True)

print()
print("=" * 74)
print("Card-generating effects respect it")
print("=" * 74)
eng, p, e = setup()
fill(p, HAND_LIMIT - 1)
jack = pool("Jack of All Trades")
jack.upgrade()          # adds 2 Colorless cards
p.hand.append(jack)
eng.play_card(p, jack)
check("Jack of All Trades+ cannot push past the limit",
      len(p.hand) <= HAND_LIMIT, True)

eng, p, e = setup()
fill(p, HAND_LIMIT - 1)
jk = pool("Jackpot")     # adds 3 free cards
p.hand.append(jk)
eng.play_card(p, jk, target=e)
check("Jackpot cannot push past the limit", len(p.hand) <= HAND_LIMIT, True)
check("...and its overflow reached the discard pile",
      len(p.discard_pile) > 0, True)

# An enemy shuffling Statuses into a full hand.
p = Player("P", 200, 99, deck=make_starter_deck())
eng = CombatEngine([p], [E.make_myte()], seed=4, scale_enemies=False)
eng.start_player_turn()
fill(p, HAND_LIMIT)
for _ in range(4):
    eng.end_player_turn()
    eng.run_enemy_turn()
    eng.start_player_turn()
    if len(p.hand) > HAND_LIMIT:
        break
check("an enemy adding Statuses cannot exceed the limit either",
      len(p.hand) <= HAND_LIMIT, True)

print()
print("=" * 74)
print("Retain no longer grows an unbounded hand")
print("=" * 74)
eng, p, e = setup()
p.draw_pile = [make_starter_deck()[0] for _ in range(40)]
sizes = []
for _ in range(6):
    p.retain_hand_turns = 1            # hand-wide Retain, every turn
    eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
    sizes.append(len(p.hand))
check("hand never exceeds the limit across 6 retained turns",
      max(sizes) <= HAND_LIMIT, True)
check("...and it does reach the limit (the test is not vacuous)",
      max(sizes), HAND_LIMIT)

print()
print("=" * 74)
print("Cards that play off the draw pile are NOT hand-limited")
print("=" * 74)
# Havoc/Cascade/Mayhem play the top card of the draw pile; it never enters
# the hand, so a full hand must not cancel them.
eng, p, e = setup()
fill(p, HAND_LIMIT)
p.draw_pile = [pool("Bludgeon") for _ in range(4)]
hp0 = e.hp
havoc = pool("Havoc")
p.hand[0] = havoc
eng.play_card(p, havoc)
check("Havoc still plays the top card with a full hand", e.hp < hp0, True)
check("...and did not find 'no card to play'",
      any("finds no card" in line for line in eng.log), False)

eng, p, e = setup()
fill(p, HAND_LIMIT)
p.draw_pile = [pool("Bludgeon") for _ in range(6)]
casc = pool("Cascade")
p.hand[0] = casc
p.energy = 3
hp0 = e.hp
eng.play_card(p, casc)
check("Cascade likewise", e.hp < hp0, True)

# take_top_of_draw reshuffles rather than fizzling on an empty draw pile.
eng, p, e = setup()
p.draw_pile = []
p.discard_pile = [make_starter_deck()[0] for _ in range(3)]
got = p.take_top_of_draw(eng.log)
check("take_top_of_draw reshuffles the discard pile in", got is not None, True)
p.draw_pile, p.discard_pile = [], []
check("...and returns None when both piles are empty",
      p.take_top_of_draw(eng.log), None)

print()
print("=" * 74)
print("Scrawl reads the shared constant")
print("=" * 74)
eng, p, e = setup()
fill(p, 3)
p.draw_pile = [make_starter_deck()[0] for _ in range(20)]
sc = pool("Scrawl")
p.hand.append(sc)
eng.play_card(p, sc)
check("Scrawl draws up to exactly the limit", len(p.hand), HAND_LIMIT)

print()
print("=" * 74)
print("Every append site goes through add_to_hand")
print("=" * 74)
import io as _io
import re
offenders = []
ENGINE_DIR = os.path.join(ROOT, "game_engine")
for fname in ("cards.py", "relics.py", "potions.py", "enemies.py", "combat.py"):
    src = _io.open(os.path.join(ENGINE_DIR, fname), encoding="utf-8").read()
    for i, line in enumerate(src.split("\n"), 1):
        if re.search(r"\bhand\.append\(", line) and "return_to_hand" not in line:
            offenders.append(f"{fname}:{i}")
check("no direct hand.append outside entities.py", offenders, [])

src = _io.open(os.path.join(ENGINE_DIR, "entities.py"), encoding="utf-8").read()
direct = [i for i, line in enumerate(src.split("\n"), 1)
          if re.search(r"\bhand\.append\(", line) and "return_to_hand" not in line]
check("entities.py appends directly in exactly 2 places "
      "(add_to_hand itself, and the draw path)", len(direct), 2)

print()
print("=" * 74)
if FAILS:
    print(f"{len(FAILS)} FAILURE(S):")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("ALL HAND-CAP CHECKS PASSED")
