# -*- coding: utf-8 -*-
"""#36 diagnostic 2: are the never-won fights UNWINNABLE, or just beyond greedy_policy?"""
import sys, io, contextlib, random
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from statistics import mean

import testing.bench as bench
import testing.play as play
from game_engine.entities import Player, seed_content
from game_engine.cards import make_starter_deck, CARD_POOL_IRONCLAD
from game_engine.combat import CombatEngine
from game_engine.relics import BURNING_BLOOD, RELIC_POOL_IRONCLAD

SEEDS = 20

SUSPECTS = [
    "The Insatiable [Hive Boss]", "Kaiser Crab [Hive Boss]",
    "Knowledge Demon [Hive Boss]", "Queen + Amalgam [Glory Boss]",
    "Test Subject [Glory Boss]", "Doormaker [Glory Boss]",
    "Aeonglass [Glory Boss]", "Mecha Knight [Glory Elite]",
    "Soul Nexus [Glory Elite]", "Knight Gang x3 [Glory Elite]",
    "Decimillipede x3 [Hive Elite]", "Devoted Sculptor [Glory]",
    "Owl Magistrate [Glory]",
]


def god_run(make_enemies, seed):
    random.seed(seed)
    seed_content(seed)
    rng = random.Random(seed)
    deck = make_starter_deck()
    for _ in range(30):
        deck.append(rng.choice(CARD_POOL_IRONCLAD)())
    for c in deck:
        c.upgrade()
    p = Player("Ironclad", max_hp=250, max_energy=6, deck=deck)
    p.add_relic(BURNING_BLOOD)
    for r in rng.sample(RELIC_POOL_IRONCLAD, 10):
        p.add_relic(r)
    engine = CombatEngine([p], make_enemies(), seed=seed, scale_enemies=False)
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
    return (engine.is_over and engine.victory), (not engine.is_over), turns


by_name = {name: mk for name, mk in play.ENCOUNTERS.values()}

print("=" * 84)
print(f"GOD-DECK PROBE  (250 HP, 6 energy, 40 cards all upgraded, 11 relics, "
      f"{SEEDS} seeds)")
print("=" * 84)
print("0% here = the fight itself is broken.  >0% = correctly ported, the")
print("policy is the limit.")
print()
print(f"{'encounter':<36} {'tier3 win':>10} {'god win':>9} {'timeouts':>9} {'turns':>7}")
for name in SUSPECTS:
    mk = by_name[name]
    with contextlib.redirect_stdout(io.StringIO()):
        res = [god_run(mk, s) for s in range(SEEDS)]
        t3 = [bench.run_encounter(mk, s, 3) for s in range(SEEDS)]
    wins = sum(1 for r in res if r[0])
    tos = sum(1 for r in res if r[1])
    t3w = 100.0 * sum(1 for r in t3 if r[0]) / len(t3)
    flag = "   <-- BROKEN?" if wins == 0 else ""
    print(f"{name:<36} {t3w:>9.0f}% {100.0*wins/len(res):>8.0f}% "
          f"{tos:>9} {mean(r[2] for r in res):>7.1f}{flag}")
