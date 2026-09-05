"""Regression: run every ENCOUNTERS entry across several seeds and player counts, asserting nothing..."""
import sys, traceback
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import testing.bench as bench
from testing.play import ENCOUNTERS

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
