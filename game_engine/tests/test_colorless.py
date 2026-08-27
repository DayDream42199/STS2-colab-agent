# -*- coding: utf-8 -*-
"""#39: the rest of the Colorless module.

Part 1 is a smoke pass -- every new card played at least once, base and
upgraded, against a punching bag. Part 2 unit-tests the mechanically
interesting ones, especially the new keywords (Retain, Ethereal) and the
cards that touch shared engine state.
"""
import os
import sys

# The modules under test live one directory up. This used to be a hardcoded
# absolute path, which is why the whole suite only ran on one machine from
# one directory -- and why it lived in a temp folder rather than the repo.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from game_engine.entities import Player
import game_engine.enemies as E
from game_engine.combat import CombatEngine
import game_engine.cards as C
from game_engine.cards import (CardType, TargetMode, COLORLESS_POOL, ANCIENT_COLORLESS,
                   CURSE_POOL, STATUS_CARDS, make_starter_deck, UNPLAYABLE)
from game_engine.statuses import StatusType

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


def setup(deck=None, players=1, hp=200):
    ps = [Player(f"P{i}", hp, 99, deck=deck or make_starter_deck())
          for i in range(players)]
    eng = CombatEngine(ps, [bag()], seed=7, scale_enemies=False)
    eng.start_player_turn()
    for p in ps:
        p.energy = 99
    return (eng, *ps, eng.enemies[0])


def find(name, pool=None):
    for f in (pool or (list(COLORLESS_POOL) + list(ANCIENT_COLORLESS)
                       + list(CURSE_POOL))):
        c = f()
        if c.name == name:
            return c
    for mk in STATUS_CARDS:
        c = mk()
        if c.name == name:
            return c
    raise KeyError(name)


def play(eng, p, card, target=None):
    p.hand = [card]
    p.energy = 99
    tgt = target if card.target == TargetMode.SINGLE_ENEMY else None
    ally = eng.other_player(p) if card.target == TargetMode.ALLY else None
    return eng.play_card(p, card, target=tgt, ally_target=ally)


print("=" * 74)
print("Part 1: every new card plays without crashing (base + upgraded)")
print("=" * 74)
crashes = []
playable = list(COLORLESS_POOL) + list(ANCIENT_COLORLESS)
for factory in playable:
    for upg in (False, True):
        try:
            eng, p, e = setup(players=2)[0], None, None
            eng, p, ally, e = setup(players=2)
            card = factory()
            if upg:
                card.upgrade()
            # Give the piles something to work with so draw/discard/pull
            # effects exercise a real path rather than an empty one.
            p.draw_pile = [C.make_starter_deck()[0] for _ in range(6)]
            p.discard_pile = [C.make_starter_deck()[1] for _ in range(4)]
            play(eng, p, card, e)
            eng.end_player_turn()
            eng.run_enemy_turn()
            eng.start_player_turn()
        except Exception as ex:
            crashes.append(f"{factory().name}{'+' if upg else ''}: {ex!r}")
check("all playable colorless cards survive a full turn", crashes, [])

# Statuses and curses are mostly unplayable; the check is that HOLDING them
# through a turn cycle is safe, which is the path that actually runs.
held_crashes = []
for mk in list(STATUS_CARDS) + list(CURSE_POOL):
    try:
        eng, p, e = setup()
        p.hand = [mk()]
        eng.end_player_turn()
        eng.run_enemy_turn()
        eng.start_player_turn()
    except Exception as ex:
        held_crashes.append(f"{mk().name}: {ex!r}")
check("all statuses/curses survive being held through a turn", held_crashes, [])

print()
print("=" * 74)
print("Part 2a: the two new keywords")
print("=" * 74)
eng, p, e = setup()
purity = find("Purity")
keep, toss = find("Wish"), C.make_starter_deck()[0]
p.hand = [purity, keep, toss]
eng.end_player_turn()
check("Retain keeps its own card in hand", [c.name for c in p.hand], ["Purity"])
check("...and non-Retain cards are discarded", len(p.discard_pile), 2)

eng, p, e = setup()
app = find("Apparition")
p.hand = [app]
eng.end_player_turn()
check("Ethereal exhausts instead of discarding", len(p.exhaust_pile), 1)
check("...and does not reach the discard pile", len(p.discard_pile), 0)

eng, p, e = setup()
app_up = find("Apparition")
app_up.upgrade()
p.hand = [app_up]
eng.end_player_turn()
check("Apparition+ LOSES Ethereal (discards instead)", len(p.discard_pile), 1)

# Ethereal must outrank a hand-wide Retain, or Void/Apparition jam forever.
eng, p, e = setup()
p.hand = [find("Void"), find("Wish")]
p.retain_hand_turns = 1
eng.end_player_turn()
check("Ethereal beats hand-wide Retain", [c.name for c in p.hand], ["Wish"])
check("...the Ethereal card exhausted", len(p.exhaust_pile), 1)

eng, p, e = setup()
anointed = find("Anointed")
check("Anointed has no Retain at base", anointed.retains_now(), False)
anointed.upgrade()
check("...and gains it on upgrade", anointed.retains_now(), True)

print()
print("=" * 74)
print("Part 2b: cards that touch shared engine state")
print("=" * 74)
eng, p, e = setup()
pb = find("Panic Button")
play(eng, p, pb, e)
check("Panic Button grants its own Block before the lockout", p.block, 30)
p.block = 0
play(eng, p, find("Ultimate Defend"), e)
check("...then cards grant no Block", p.block, 0)
p.block = 0
p.gain_block_noncard(9)
check("...but relics/powers still can", p.block, 9)

eng, p, e = setup()
play(eng, p, find("Fasten"), e)
d = [c for c in make_starter_deck() if c.name == "Defend"][0]
p.block = 0
play(eng, p, d, e)
check("Fasten adds to Defend (5 + 4)", p.block, 9)

eng, p, e = setup()
p.hand = [find("Sloth")]
for _ in range(3):
    s = make_starter_deck()[0]
    p.hand.append(s)
    eng.play_card(p, s, target=e)
check("Sloth allows exactly 3 plays", p.cards_played_this_turn, 3)
extra = make_starter_deck()[0]
p.hand.append(extra)
check("...and blocks the 4th", eng.play_card(p, extra, target=e), False)

eng, p, e = setup()
enth = find("Enthralled")
other = make_starter_deck()[0]
p.hand = [other, enth]
check("Enthralled blocks other cards", eng.play_card(p, other, target=e), False)
check("...and is itself playable", eng.play_card(p, enth), True)
check("...after which the other card plays", eng.play_card(p, other, target=e), True)

eng, p, e = setup()
clash = find("Clash")
defend = [c for c in make_starter_deck() if c.name == "Defend"][0]
p.hand = [clash, defend]   # a Defend in hand
check("Clash refuses with a non-Attack in hand", eng.play_card(p, clash, target=e), False)
p.hand = [clash, make_starter_deck()[0]]   # all Attacks
check("...and plays when every card is an Attack", eng.play_card(p, clash, target=e), True)

eng, p, e = setup()
p.hp = 100
gambit = find("The Gambit")
play(eng, p, gambit, e)
check("The Gambit grants its Block", p.block, 50)
p.block = 0
p.take_damage(5, source_is_attack=True, log=eng.log, label="test", attacker=e)
check("...and any unblocked attack kills you", p.alive, False)

eng, p, e = setup()
p.draw_pile = [find("Void")] + [make_starter_deck()[0] for _ in range(3)]
p.energy = 3
p.draw_cards(4, eng.log)
check("Void costs 1 energy when drawn", p.energy, 2)

eng, p, e = setup()
p.hand = [find("Mind Rot")]
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("Mind Rot draws 1 fewer, from the discard pile too", len(p.hand), 4)

eng, p, e = setup()
p.hand = [find("Waste Away")]
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("Waste Away costs 1 energy per turn", p.energy, p.max_energy - 1)

print()
print("=" * 74)
print("Part 2c: deferred effects and returning cards")
print("=" * 74)
eng, p, e = setup()
play(eng, p, find("Toric Toughness"), e)
check("Toric Toughness pays out now", p.block, 5)
p.block = 0
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("...and again next turn", p.block, 5)
p.block = 0
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("...and the turn after", p.block, 5)
p.block = 0
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("...then stops (2 extra turns only)", p.block, 0)

eng, p, e = setup()
hatchet = find("Thrumming Hatchet")
play(eng, p, hatchet, e)
check("Thrumming Hatchet leaves hand when played", hatchet in p.hand, False)
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("...and returns next turn", hatchet in p.hand, True)

eng, p, e = setup()
hp0 = e.hp
play(eng, p, find("The Bomb"), e)
check("The Bomb does nothing immediately", e.hp, hp0)
for _ in range(2):
    eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("...nor after 2 turns", e.hp, hp0)
e.block = 0   # cleared right before the bomb lands, not a phase earlier
eng.end_player_turn()
check("...and detonates at the end of the 3rd", hp0 - e.hp, 40)

eng, p, e = setup()
p.block = 12
play(eng, p, find("Prolong"), e)
p.block = 0
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("Prolong repays the snapshotted Block", p.block, 12)

print()
print("=" * 74)
print("Part 2d: counting and escalating cards")
print("=" * 74)
eng, p, e = setup()
for _ in range(4):
    s = make_starter_deck()[0]
    p.hand = [s]
    eng.play_card(p, s, target=e)
axe = find("Gold Axe")
hp0 = e.hp
play(eng, p, axe, e)
check("Gold Axe deals damage = cards played this combat", hp0 - e.hp, 4)

eng, p, e = setup()
m1, m2 = find("Maul"), find("Maul")
p.draw_pile.append(m2)
hp0 = e.hp
play(eng, p, m1, e)
check("Maul hits twice for 5", hp0 - e.hp, 10)
p.draw_pile.remove(m2)
p.hand = [m2]
hp0 = e.hp
play(eng, p, m2, e)
check("...and a second Maul already carries the +2", hp0 - e.hp, 14)

eng, p, e = setup()
play(eng, p, find("Panache"), e)
hp0 = e.hp
for _ in range(4):
    s = make_starter_deck()[0]
    p.hand = [s]
    eng.play_card(p, s, target=e)
dealt = hp0 - e.hp
check("Panache counts itself, so the 4th Strike is the 5th play", dealt, 4 * 6 + 10)
s = make_starter_deck()[0]
p.hand = [s]
hp0 = e.hp
eng.play_card(p, s, target=e)
check("...and the next Strike is plain again", hp0 - e.hp, 6)

eng, p, e = setup()
play(eng, p, find("Automation"), e)
p.draw_pile = [make_starter_deck()[0] for _ in range(12)]
p.energy = 0
p.cards_drawn_this_combat = 0
p.draw_cards(9, eng.log)
check("Automation is silent before the 10th draw", p.energy, 0)
p.draw_cards(1, eng.log)
check("...and pays out on it", p.energy, 1)

eng, p, e = setup()
boulder = find("Rolling Boulder")
play(eng, p, boulder, e)
hp0 = e.hp
eng.end_player_turn(); eng.run_enemy_turn()
e.block = 0
eng.start_player_turn()
check("Rolling Boulder deals 5 on the next turn", hp0 - e.hp, 5)
hp0 = e.hp
eng.end_player_turn(); eng.run_enemy_turn()
e.block = 0   # the bag blocks on its own turn; Boulder lands on start_turn
eng.start_player_turn()
check("...then 10", hp0 - e.hp, 10)

print()
print("=" * 74)
print("Part 2e: draw-pile placement")
print("=" * 74)
eng, p, e = setup()
play(eng, p, find("Nostalgia"), e)
s = make_starter_deck()[0]
p.hand = [s]
n0 = len(p.draw_pile)
eng.play_card(p, s, target=e)
check("Nostalgia puts the first Attack on the draw pile", len(p.draw_pile), n0 + 1)
s2 = make_starter_deck()[0]
p.hand = [s2]
n1, d1 = len(p.draw_pile), len(p.discard_pile)
eng.play_card(p, s2, target=e)
check("...but only the first each turn", (len(p.draw_pile), len(p.discard_pile)),
      (n1, d1 + 1))

eng, p, e = setup()
play(eng, p, find("Rebound"), e)
s = make_starter_deck()[0]
p.hand = [s]
n0 = len(p.draw_pile)
eng.play_card(p, s, target=e)
check("Rebound puts the next card on the draw pile", len(p.draw_pile), n0 + 1)

print()
print("=" * 74)
print("Part 2f: coop cards (2 players)")
print("=" * 74)
eng, p, ally, e = setup(players=2)
ally.energy = 0
play(eng, p, find("Believe in You"), e)
check("Believe in You gives the ally 2 energy", ally.energy, 2)

eng, p, ally, e = setup(players=2)
ally.block = 0
play(eng, p, find("Lift"), e)
check("Lift gives the ally 11 block", ally.block, 11)

eng, p, ally, e = setup(players=2)
ally.block = 17
p.block = 0
play(eng, p, find("Mimic"), e)
check("Mimic mirrors the ally's block", p.block, 17)

eng, p, ally, e = setup(players=2)
play(eng, p, find("Coordinate"), e)
check("Coordinate gives the ally 5 Strength this turn",
      ally.get_status(StatusType.STRENGTH_THIS_TURN), 5)

eng, p, ally, e = setup(players=2)
gu = find("Gang Up")
hp0 = e.hp
play(eng, p, gu, e)
check("Gang Up is a flat 5 with no ally hits", hp0 - e.hp, 5)
s = make_starter_deck()[0]
ally.hand = [s]
eng.play_card(ally, s, target=e)
gu2 = find("Gang Up")
hp0 = e.hp
play(eng, p, gu2, e)
check("...and 5 + 5 after the ally attacks once", hp0 - e.hp, 10)

eng, p, ally, e = setup(players=2)
play(eng, p, find("Knockdown"), e)
hp0 = e.hp
s = make_starter_deck()[0]
ally.hand = [s]
eng.play_card(ally, s, target=e)
check("Knockdown doubles the ALLY's damage (6 -> 12)", hp0 - e.hp, 12)
hp0 = e.hp
s2 = make_starter_deck()[0]
p.hand = [s2]
eng.play_card(p, s2, target=e)
check("...but not the caster's own", hp0 - e.hp, 6)

eng, p, ally, e = setup(players=2)
play(eng, p, find("Beacon of Hope"), e)
ally.block = 0
p.block = 0
play(eng, p, find("Ultimate Defend"), e)
check("Beacon of Hope shares half the Block with the ally", ally.block, 11 // 2)

eng, p, ally, e = setup(players=2)
play(eng, p, find("Intercept"), e)
check("Intercept registers the ally as covered", ally in p.redirect_attacks_from, True)
check("...and enemy targeting redirects to the interceptor",
      eng.pick_enemy_attack_target() is p, True)

print()
print("=" * 74)
print("Part 2g: curse and status penalties")
print("=" * 74)
eng, p, e = setup()
p.hp = 100
p.hand = [find("Bad Luck")]
eng.end_player_turn()
check("Bad Luck costs 13 HP (Block does not stop it)", p.hp, 87)

eng, p, e = setup()
p.hand = [find("Doubt")]
eng.end_player_turn()
check("Doubt applies Weak", p.get_status(StatusType.WEAK), 1)

eng, p, e = setup()
p.hand = [find("Shame")]
eng.end_player_turn()
check("Shame applies Frail", p.get_status(StatusType.FRAIL), 1)

eng, p, e = setup()
p.hp = 100
p.hand = [find("Regret"), make_starter_deck()[0], make_starter_deck()[1]]
eng.end_player_turn()
check("Regret costs 1 HP per card in hand, itself included", p.hp, 97)

eng, p, e = setup()
p.hp = 100
p.block = 50
p.hand = [find("Decay")]
eng.end_player_turn()
check("Decay deals damage, which Block absorbs", p.hp, 100)

print()
print("=" * 74)
print("Part 3: coverage and bookkeeping")
print("=" * 74)
check("COLORLESS_POOL size", len(COLORLESS_POOL), 91)
check("ANCIENT_COLORLESS size", len(ANCIENT_COLORLESS), 9)
check("CURSE_POOL size", len(CURSE_POOL), 18)
check("STATUS_CARDS size", len(STATUS_CARDS), 7)

bad_rarity = sorted({f().name for f in COLORLESS_POOL if f().rarity != "Colorless"})
check("every COLORLESS_POOL card has rarity Colorless", bad_rarity, [])
bad_anc = sorted({f().name for f in ANCIENT_COLORLESS if f().rarity != "Ancient"})
check("every ANCIENT_COLORLESS card has rarity Ancient", bad_anc, [])
bad_curse = sorted({f().name for f in CURSE_POOL if f().rarity != "Curse"})
check("every curse has rarity Curse", bad_curse, [])

# Colorless must never leak into the Ironclad reward tiers.
iron = {f().name for f in C.CARD_POOL_IRONCLAD}
leak = sorted(iron & {f().name for f in COLORLESS_POOL})
check("no Colorless card leaks into CARD_POOL_IRONCLAD", leak, [])

# Unplayable really is unplayable, even with infinite energy.
eng, p, e = setup()
unplayable = [mk() for mk in STATUS_CARDS if mk().cost == UNPLAYABLE]
unplayable += [f() for f in CURSE_POOL if f().cost == UNPLAYABLE]
p.hand = list(unplayable)
p.energy = 999
check("no unplayable status/curse appears in playable_cards",
      [c.name for c in eng.playable_cards(p) if c in unplayable], [])

dupes = [n for n in {f().name for f in COLORLESS_POOL}
         if sum(1 for f in COLORLESS_POOL if f().name == n) > 1]
check("no duplicate names in COLORLESS_POOL", sorted(dupes), [])

print()
print("=" * 74)
if FAILS:
    print(f"{len(FAILS)} FAILURE(S):")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("ALL COLORLESS CHECKS PASSED")
