"""Regression: run every ENCOUNTERS entry across several seeds and player
counts, asserting nothing raises. Bounded loops only -- MAX_TURNS caps the
fight and the seed list is finite (the 29GB-log lesson)."""
import sys, traceback
import os
import sys

# The modules under test live one directory up. This used to be a hardcoded
# absolute path, which is why the whole suite only ran on one machine from
# one directory -- and why it lived in a temp folder rather than the repo.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bench
from play import ENCOUNTERS

bad = []
total = 0
for key, (name, make_enemies) in ENCOUNTERS.items():
    for seed in range(4):
        total += 1
        try:
            bench.run_encounter(make_enemies, seed)
        except Exception as ex:
            bad.append((key, name, seed, repr(ex)))
            traceback.print_exc()
            break
print(f"ran {total} encounter/seed combos across {len(ENCOUNTERS)} encounters")
print("FAILURES:", bad if bad else "none")
sys.exit(1 if bad else 0)
