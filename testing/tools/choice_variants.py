# -*- coding: utf-8 -*-
"""Which choice heuristic actually beats random?

The first attempt (damage+block, Powers +12, min for exhaust) LOST to
random by 4pp. Rather than guess at why, this scores several resolvers on
the same decks and seeds, and isolates which PROMPT KIND is responsible by
running each kind greedily with everything else random.
"""
import sys, io, contextlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import random
from statistics import mean

import game_engine.cards as C
from game_engine.cards import CardType
import testing.bench as bench
from choice_ab import run, TARGETS, SEEDS as _S

SEEDS = 60


def value_plain(card):
    if card.card_type in (CardType.STATUS, CardType.CURSE):
        return -100.0
    v = float(card.val("damage") + card.val("block"))
    if card.card_type == CardType.POWER:
        v += 12.0
    if card.upgraded:
        v += 2.0
    return v


def value_per_energy(card):
    """Same, but per point of energy. greedy_policy has 3 energy a turn and
    plays ONE card per decision, so a 3-cost bomb it can only cast alone is
    not obviously better than two cheap cards."""
    if card.card_type in (CardType.STATUS, CardType.CURSE):
        return -100.0
    cost = card.cost if isinstance(card.cost, int) else 3
    v = float(card.val("damage") + card.val("block"))
    if card.card_type == CardType.POWER:
        v += 12.0
    return v / max(1, cost)


def make_resolver(value_fn, kinds=None):
    """Greedy on `kinds` (all of them if None), random elsewhere."""
    def resolver(engine, player, options, prompt, kind):
        if kinds is not None and kind not in kinds:
            return player.rng.choice(options)
        if kind in ("exhaust", "transform"):
            return min(options, key=value_fn)
        return max(options, key=value_fn)
    return resolver


def junk_only(engine, player, options, prompt, kind):
    """Only act on prompts where the right answer is unambiguous: throw away
    a Status or Curse if one is on offer, otherwise defer to random."""
    if kind in ("exhaust", "transform"):
        junk = [c for c in options
                if c.card_type in (CardType.STATUS, CardType.CURSE)]
        if junk:
            return junk[0]
        return player.rng.choice(options)
    junk = [c for c in options
            if c.card_type not in (CardType.STATUS, CardType.CURSE)]
    return player.rng.choice(junk) if junk else options[0]


def score(resolver):
    total = 0.0
    hp = []
    for name, mk in TARGETS:
        with contextlib.redirect_stdout(io.StringIO()):
            res = [run(mk, s, resolver, 8, 8) for s in range(SEEDS)]
        total += 100.0 * sum(1 for w in res if w[0]) / SEEDS
        hp += [80 - h for w, h in res if w]
    return total / len(TARGETS), (mean(hp) if hp else 0.0)


SHED = {"exhaust", "transform", "stash"}


def make_resolver2(value_fn, kinds=None):
    """As make_resolver, but with `stash` (Thinking Ahead) counted as a
    SHED prompt -- it takes a card out of your hand, so you want the worst
    one, the opposite of Headbutt's to_draw_top."""
    def resolver(engine, player, options, prompt, kind):
        if kinds is not None and kind not in kinds:
            return player.rng.choice(options)
        if kind in SHED:
            return min(options, key=value_fn)
        return max(options, key=value_fn)
    return resolver


ARMS = [
    ("random (old behaviour)", None),
    ("v2: stash split out, all kinds", make_resolver2(value_plain)),
    ("v2: to_hand + copy + to_draw_top only",
     make_resolver2(value_plain, {"to_hand", "copy", "to_draw_top"})),
    ("v2: gain-side + shed-side, no upgrade",
     make_resolver2(value_plain, {"to_hand", "copy", "to_draw_top",
                                  "exhaust", "transform", "stash"})),
    ("plain value, all kinds", make_resolver(value_plain)),
    ("per-energy value, all kinds", make_resolver(value_per_energy)),
    ("junk-only (defer when unclear)", junk_only),
    ("plain value, to_hand only", make_resolver(value_plain, {"to_hand"})),
    ("plain value, upgrade only", make_resolver(value_plain, {"upgrade"})),
    ("plain value, exhaust only", make_resolver(value_plain, {"exhaust"})),
    ("plain value, everything BUT exhaust",
     make_resolver(value_plain, {"to_hand", "upgrade", "copy",
                                 "to_draw_top", "transform"})),
]

print("=" * 74)
print(f"CHOICE RESOLVER A/B  ({SEEDS} seeds x {len(TARGETS)} encounters)")
print("=" * 74)
print(f"{'resolver':<38} {'win%':>7} {'HP lost':>9}")
base = None
for label, r in ARMS:
    w, h = score(r)
    if base is None:
        base = w
    print(f"{label:<38} {w:>6.1f}% {h:>8.1f}   {w - base:+.1f}")
