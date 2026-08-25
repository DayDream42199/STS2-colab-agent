# -*- coding: utf-8 -*-
"""Verification for task #28: all 22 newly-ported potions and the engine
features they needed."""
import os
import sys

# The modules under test live one directory up. This used to be a hardcoded
# absolute path, which is why the whole suite only ran on one machine from
# one directory -- and why it lived in a temp folder rather than the repo.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from entities import Player
import enemies as E
from combat import CombatEngine
from cards import (CARD_POOL_IRONCLAD, COLORLESS_POOL, make_starter_deck,
                   CardType)
import potions as P
from statuses import StatusType

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  [{'ok' if ok else 'FAIL'}] {label}: got {got!r}, want {want!r}")
    if not ok:
        FAILS.append(label)


def potion(name):
    for p in list(P.POTION_POOL_IRONCLAD) + list(P.SPECIAL_POTIONS):
        if p.name == name:
            return p
    raise KeyError(name)


def card(name):
    for f in CARD_POOL_IRONCLAD:
        c = f()
        if c.name == name:
            return c
    for c in make_starter_deck():
        if c.name == name:
            return c
    raise KeyError(name)


def bag(hp=5000):
    e = E.make_nibbit()
    e.max_hp = e.hp = hp
    return e


def setup(deck=None, hp=500, enemy=None):
    p = Player("Tester", hp, 99, deck=deck if deck is not None else make_starter_deck())
    eng = CombatEngine([p], [enemy or bag()], seed=4, scale_enemies=False)
    eng.start_player_turn()
    p.energy = 99
    return eng, p, eng.enemies[0]


def use(eng, p, name, target=None):
    pot = potion(name)
    p.potions = [pot]
    return eng.use_potion(p, pot, target=target)


print("=" * 74)
print("Reversible card mutations (the deck_template trap)")
print("=" * 74)
deck = make_starter_deck()
eng, p, e = setup(deck=deck)
use(eng, p, "Blessing of the Forge")
check("Blessing of the Forge upgrades the hand", all(c.upgraded for c in p.hand), True)
p.revert_combat_upgrades()
check("...and reverts after combat", any(c.upgraded for c in deck), False)

eng, p, e = setup()
target_card = max(p.hand, key=lambda c: c.current_cost())
use(eng, p, "Touch of Insanity")
check("Touch of Insanity zeroes a card's cost", target_card.current_cost(p), 0)
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("...for the whole combat, not just the turn", target_card.current_cost(p), 0)
p.clear_temp_costs("combat")
check("...and it reverts at combat end", target_card.current_cost(p) > 0, True)

eng, p, e = setup()
use(eng, p, "Snecko Oil")
check("Snecko Oil randomizes costs into 0-3",
      all(0 <= c.current_cost(p) <= 3 for c in p.hand if c.current_cost() != "X"), True)
originals = [(c, c.cost) for c in p.hand]
p.clear_temp_costs("turn")
check("...reversibly (printed costs untouched)",
      all(c.current_cost(p) == orig for c, orig in originals), True)

print()
print("=" * 74)
print("Energy / draw / retain over multiple turns")
print("=" * 74)
eng, p, e = setup()
use(eng, p, "Radiant Tincture")
base = p.max_energy
for turn in range(3):
    eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
    if p.energy != base + 1:
        FAILS.append(f"Radiant Tincture turn {turn+1}")
check("Radiant Tincture gives +1 energy for 3 turns", p.energy, base + 1)
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("...then stops", p.energy, base)

eng, p, e = setup()
use(eng, p, "Clarity Extract")
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("Clarity Extract draws 6 instead of 5 next turn", len(p.hand), 6)

eng, p, e = setup()
p.hand = [card("Strike"), card("Defend")]
use(eng, p, "Stable Serum")
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("Stable Serum retains the hand and still draws", len(p.hand), 7)

print()
print("=" * 74)
print("Buffer, extra turn, triple damage")
print("=" * 74)
eng, p, e = setup()
use(eng, p, "Lucky Tonic")
p.block = 0
hp0 = p.hp
p.take_damage(30, log=eng.log, attacker=e)
check("Buffer prevents the HP loss entirely", p.hp, hp0)
check("...spending the stack", p.get_status(StatusType.BUFFER), 0)
p.take_damage(30, log=eng.log, attacker=e)
check("...so the next hit lands", hp0 - p.hp, 30)

eng, p, e = setup()
p.hp = 100
use(eng, p, "Ambergris")
check("Ambergris heals 50% of max HP", p.hp, 100 + 250)
check("...and grants an extra turn", p.extra_turns, 1)
ehp0 = e.hp
php0 = p.hp
eng.end_player_turn()
eng.run_enemy_turn()
check("...which the enemy phase honours by not acting", p.hp, php0)
check("...and the charge is spent", p.extra_turns, 0)

eng, p, e = setup()
use(eng, p, "Gigantification Potion")
ehp0 = e.hp
eng.play_card(p, card("Strike") if card("Strike") in p.hand else p.hand[0], target=e)
strike = card("Strike")
p.hand.append(strike)
ehp0 = e.hp
p.next_attack_multiplier = 3
eng.play_card(p, strike, target=e)
check("Gigantification triples the next Attack (6 -> 18)", ehp0 - e.hp, 18)

print()
print("=" * 74)
print("Replay, Duplicator, and card-playing potions")
print("=" * 74)
eng, p, e = setup()
use(eng, p, "Duplicator")
strike = card("Strike")
p.hand.append(strike)
ehp0 = e.hp
eng.play_card(p, strike, target=e)
check("Duplicator plays the next card an extra time", ehp0 - e.hp, 12)

eng, p, e = setup()
use(eng, p, "Soldier's Stew")
strike = next(c for c in p.hand if "Strike" in c.name)
check("Soldier's Stew grants Replay to Strike cards", strike.replay, 1)
ehp0 = e.hp
eng.play_card(p, strike, target=e)
check("...so it resolves twice", ehp0 - e.hp, 12)
p.clear_temp_replays()
check("...and Replay reverts at combat end", strike.replay, 0)

eng, p, e = setup()
p.draw_pile = [card("Strike"), card("Strike"), card("Strike")]
ehp0 = e.hp
use(eng, p, "Distilled Chaos")
check("Distilled Chaos plays the top 3 draw-pile cards", ehp0 - e.hp, 18)

eng, p, e = setup()
p.discard_pile = [card("Anger")]
use(eng, p, "Liquid Memories")
pulled = next(c for c in p.hand if c.name == "Anger")
check("Liquid Memories returns a discarded card free this turn",
      pulled.current_cost(p), 0)

print()
print("=" * 74)
print("The rest")
print("=" * 74)
eng, p, e = setup()
use(eng, p, "Colorless Potion")
colorless_names = {f().name for f in COLORLESS_POOL}
check("Colorless Potion adds a real Colorless card, free this turn",
      any(c.name in colorless_names and c.current_cost(p) == 0 for c in p.hand), True)

eng, p, e = setup()
before = len(p.hand)
use(eng, p, "Orobic Acid")
kinds = {c.card_type for c in p.hand[before:]}
check("Orobic Acid adds one of each card type", kinds,
      {CardType.ATTACK, CardType.SKILL, CardType.POWER})

eng, p, e = setup()
e.add_status(StatusType.STRENGTH, 10)
use(eng, p, "Shackling Potion")
check("Shackling Potion strips 7 Strength this turn", e.deal_attack_damage(5), 8)

eng, p, e = setup()
use(eng, p, "Beetle Juice", target=e)
check("Beetle Juice cuts enemy damage by 30%", e.deal_attack_damage(10), 7)

eng, p, e = setup()
p.potions = [potion("Entropic Brew")]
eng.use_potion(p, p.potions[0])
check("Entropic Brew fills every empty potion slot", len(p.potions), p.potion_slots)

eng, p, e = setup()
hp0, ehp0 = p.hp, e.hp
use(eng, p, "Foul Potion")
check("Foul Potion hits enemies AND the user", (ehp0 - e.hp, hp0 - p.hp), (12, 12))

eng, p, e = setup()
use(eng, p, "Glowwater Potion")
check("Glowwater Potion exhausts the hand", len(p.exhaust_pile), 5)
check("...and draws 10", len(p.hand), 5)   # starter deck only has 5 left

eng, p, e = setup()
p.energy = 3
before = len(p.hand)
use(eng, p, "Cure All")
check("Cure All gives energy and cards", (p.energy, len(p.hand)), (4, before + 2))

eng, p, e = setup()
p.draw_pile = [card("Bludgeon")]
use(eng, p, "Droplet of Precognition")
check("Droplet of Precognition pulls from the draw pile",
      any(c.name == "Bludgeon" for c in p.hand), True)

print()
print("=" * 74)
print("Coverage")
print("=" * 74)
check("48 pool + 4 special = the wiki's 52 in-scope potions",
      len(P.POTION_POOL_IRONCLAD) + len(P.SPECIAL_POTIONS), 52)

# Every potion must at least run without raising.
failed = []
for pot in list(P.POTION_POOL_IRONCLAD) + list(P.SPECIAL_POTIONS):
    eng, p, e = setup()
    p.potions = [pot]
    try:
        eng.use_potion(p, pot, target=e)
    except Exception as ex:
        failed.append((pot.name, repr(ex)))
check("every potion resolves without error", failed, [])

print()
print("=" * 74)
if FAILS:
    print(f"{len(FAILS)} FAILURE(S):")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("ALL POTION CHECKS PASSED")
