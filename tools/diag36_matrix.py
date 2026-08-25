# -*- coding: utf-8 -*-
"""#36 diagnostic 1: deck ablation matrix.

Runs EVERY encounter against all three deck tiers, not just the one its
region is assigned. Three questions at once:

  * Are Act 1/2 normals still ~100% on a bare starter deck? If yes,
    DECK_TIERS is not what makes them walkovers.
  * Do the 0% Act 1 elites/bosses become winnable with a bigger deck? If
    yes they are not mis-ported -- they are being measured with a deck no
    real player would still have when they reach them.
  * Does win rate move at all for the saturated groups, or is it pinned?
"""
import sys, io, contextlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from statistics import mean

import bench
import play

SEEDS = 20


def measure(make_enemies, tier):
    res = [bench.run_encounter(make_enemies, s, tier) for s in range(SEEDS)]
    wins = [r for r in res if r[0]]
    wr = 100.0 * len(wins) / len(res)
    # HP lost is measured on WINS only; a loss is always "80 lost" and would
    # drag the average toward the win rate instead of adding information.
    hp_lost = mean(80 - r[3] for r in wins) if wins else float("nan")
    return wr, hp_lost


rows = []
for key, (name, make_enemies) in play.ENCOUNTERS.items():
    region = bench.region_of(name)
    tier = bench.tier_of(make_enemies)
    with contextlib.redirect_stdout(io.StringIO()):
        cells = [measure(make_enemies, t) for t in (1, 2, 3)]
    rows.append((region, tier, name, cells))
    print(f"done: {name}", file=sys.stderr)

ORDER = ["Act 1  Overgrowth", "Act 1  Underdocks", "Act 2  Hive",
         "Act 3  Glory", "Event-only"]

print("=" * 92)
print("DECK ABLATION -- every encounter vs all three deck tiers "
      f"({SEEDS} seeds each)")
print("=" * 92)
print("win% (and avg HP lost on wins) for deck tier 1 / 2 / 3")
print()

for region in ORDER:
    for tier in ("normal", "elite", "boss"):
        block = [r for r in rows if r[0] == region and r[1] == tier]
        if not block:
            continue
        print(f"-- {region}  |  {tier}s")
        print(f"   {'encounter':<40} {'tier1':>14} {'tier2':>14} {'tier3':>14}")
        for _, _, name, cells in sorted(block, key=lambda r: r[3][0][0]):
            cs = "".join(
                f"{wr:>7.0f}% {('-' if hp != hp else f'{hp:.0f}hp'):>6}"
                for wr, hp in cells)
            print(f"   {name:<40}{cs}")
        for i, label in enumerate(("tier1", "tier2", "tier3")):
            wrs = [c[3][i][0] for c in block]
            print(f"   {'':<40} {label} mean {mean(wrs):>5.1f}%  "
                  f"median {sorted(wrs)[len(wrs)//2]:>5.1f}%")
        print()

print("=" * 92)
print("SUMMARY -- normals only, mean vs median win rate")
print("=" * 92)
print(f"{'region':<22} {'n':>3} {'t1 mean':>9} {'t1 med':>8} "
      f"{'t2 mean':>9} {'t3 mean':>9} {'t1 hp lost':>11}")
for region in ORDER:
    block = [r for r in rows if r[0] == region and r[1] == "normal"]
    if not block:
        continue
    w1 = [c[3][0][0] for c in block]
    w2 = [c[3][1][0] for c in block]
    w3 = [c[3][2][0] for c in block]
    hp1 = [c[3][0][1] for c in block if c[3][0][1] == c[3][0][1]]
    print(f"{region:<22} {len(block):>3} {mean(w1):>8.1f}% "
          f"{sorted(w1)[len(w1)//2]:>7.1f}% {mean(w2):>8.1f}% "
          f"{mean(w3):>8.1f}% {mean(hp1):>10.1f}")
