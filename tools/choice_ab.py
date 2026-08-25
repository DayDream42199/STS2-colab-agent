# -*- coding: utf-8 -*-
"""#45: does choosing well actually change anything?

The headline benchmark barely moved, which is expected and says nothing:
its fixed-deck column is Strike/Defend/Bash (no choice cards at all), and
the ladder column draws 13 choice cards out of a 186-card pool, so most
runs never see one.

This isolates the effect instead: a deck built AROUND the choice cards,
run with the random resolver (the old behaviour) against the heuristic one.
"""
import sys, io, contextlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import random
from statistics import mean

from entities import Player, seed_content
from combat import CombatEngine
from relics import BURNING_BLOOD
import cards as C
from cards import make_starter_deck
import bench
import play

SEEDS = 60

CHOICE_CARDS = ["Armaments", "Headbutt", "True Grit", "Wish", "Seeker Strike",
                "Discovery", "Abundance", "Dual Wield", "Thinking Ahead",
                "Neow's Fury", "Purity", "Stratagem", "Entropy"]


def factory_for(name):
    for f in (list(C.CARD_POOL_IRONCLAD) + list(C.ANCIENT_CARDS_IRONCLAD)
              + list(C.COLORLESS_POOL) + list(C.ANCIENT_COLORLESS)):
        if f().name == name:
            return f
    raise KeyError(name)


CHOICE_FACTORIES = [factory_for(n) for n in CHOICE_CARDS]


def build_deck(rng, choice_copies, filler):
    """Starter deck + N choice cards + filler pool cards, so both arms
    fight with the same deck SIZE and differ only in the resolver."""
    deck = make_starter_deck()
    for _ in range(choice_copies):
        deck.append(rng.choice(CHOICE_FACTORIES)())
    for _ in range(filler):
        deck.append(rng.choice(C.CARD_POOL_IRONCLAD)())
    return deck


def run(make_enemies, seed, resolver, choice_copies, filler):
    random.seed(seed)
    seed_content(seed)   # enemy HP has its own stream now -- see enemies.py
    rng = random.Random(seed)
    p = Player("Ironclad", max_hp=80, max_energy=3,
               deck=build_deck(rng, choice_copies, filler))
    p.add_relic(BURNING_BLOOD)
    engine = CombatEngine([p], make_enemies(), seed=seed, scale_enemies=False)
    engine.choice_resolver = resolver
    engine.start_player_turn()
    turns = 0
    while not engine.is_over and turns < bench.MAX_TURNS:
        turns += 1
        bench.take_player_turn(engine, p)
        if engine.is_over:
            break
        engine.end_player_turn()
        if engine.is_over:
            break
        engine.run_enemy_turn()
        if engine.is_over:
            break
        engine.start_player_turn()
    won = engine.is_over and engine.victory
    return won, max(0, p.hp)


ENCOUNTERS = [(name, mk) for name, mk in play.ENCOUNTERS.values()]
# A spread of real fights that the greedy policy does not already trivially
# win or trivially lose -- a saturated encounter cannot show a difference.
TARGETS = [(n, mk) for n, mk in ENCOUNTERS
           if n in ("Byrdonis (Elite)", "Terror Eel [UD Elite]",
                    "Skulking Colony [UD Elite]", "Mysterious Knight [Hive]",
                    "Slumbering Beetle [Hive]", "Tunneler [Hive]",
                    "The Obscura [Hive]", "Louse Progenitor [Hive]",
                    "Axebot [Glory]", "Globe Head [Glory]",
                    "The Merchant??? [Event]", "Infested Prism [Hive Elite]")]

print("=" * 78)
print(f"CHOICE-CARD A/B  ({SEEDS} seeds, deck = starter + 8 choice cards + 8 filler)")
print("=" * 78)
print("random  = the old behaviour (no resolver installed)")
print("greedy  = bench.greedy_choice")
print()
print(f"{'encounter':<34} {'random':>10} {'greedy':>10} {'delta':>8}")

tot_r = tot_g = 0
for name, mk in TARGETS:
    with contextlib.redirect_stdout(io.StringIO()):
        wr = [run(mk, s, None, 8, 8) for s in range(SEEDS)]
        wg = [run(mk, s, bench.greedy_choice, 8, 8) for s in range(SEEDS)]
    r = 100.0 * sum(1 for w in wr if w[0]) / SEEDS
    g = 100.0 * sum(1 for w in wg if w[0]) / SEEDS
    tot_r += r
    tot_g += g
    flag = ""
    if abs(g - r) >= 5:
        flag = "  <--"
    print(f"{name:<34} {r:>9.0f}% {g:>9.0f}% {g - r:>+7.0f}{flag}")

print("-" * 78)
print(f"{'MEAN':<34} {tot_r/len(TARGETS):>9.1f}% {tot_g/len(TARGETS):>9.1f}% "
      f"{(tot_g - tot_r)/len(TARGETS):>+7.1f}")

# And the same thing on HP lost, which does not saturate.
print()
print("HP lost on wins (lower is better):")
for name, mk in TARGETS[:6]:
    with contextlib.redirect_stdout(io.StringIO()):
        wr = [run(mk, s, None, 8, 8) for s in range(SEEDS)]
        wg = [run(mk, s, bench.greedy_choice, 8, 8) for s in range(SEEDS)]
    hr = [80 - hp for w, hp in wr if w]
    hg = [80 - hp for w, hp in wg if w]
    if hr and hg:
        print(f"  {name:<32} {mean(hr):>6.1f} -> {mean(hg):>6.1f} "
              f"({mean(hg) - mean(hr):+.1f})")
