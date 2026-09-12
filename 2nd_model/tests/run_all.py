"""Run every offline check and report one verdict.

    python tests/run_all.py            everything offline (a few seconds)
    python tests/run_all.py fork cost  only the suites whose name contains these

Each script is its own process and exits non-zero on any failure, so this
needs nothing from their output but the tail. The live socket tests are not
run from here: start a server first, then run tests/live/live2p.py, or
tests/live/choice_server.py followed by tests/live/live_choice.py.
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

# Order: the cheap unit suites first, then the whole-registry checks.
SCRIPTS = [
    "test_slice.py",       # card values against the reference, first batch
    "test_free21.py",
    "test_random.py",
    "test_oneoffs.py",
    "test_intercept.py",   # play interception
    "test_cost.py",
    "test_counters2.py",
    "test_reactive.py",
    "test_fork.py",        # card identity, upgrades, and every batch since
    "test_choice.py",      # player choice through Session
    "test_enemies.py",     # scripted enemies, co-op scaling, The Insatiable
    "test_review.py",
    "test_bughunt.py",
    "audit_structure.py",  # every card / status / effect / upgrade entry is well-formed
    "sweep.py",            # every card played plain, upgraded, and with Replay
    "card_matrix.py all",  # every card through every situation, illegal moves included
    "determinism.py",      # same seed, same fight
    "fuzz.py",             # 300 random fights across the whole registry
]


def main(argv):
    wanted = [s for s in SCRIPTS if not argv or any(a in s for a in argv)]
    if not wanted:
        print("nothing matches", argv)
        return 2

    failed = []
    started = time.time()
    for script in wanted:
        t = time.time()
        name, *args = script.split()
        proc = subprocess.run([sys.executable, os.path.join(HERE, name)] + args,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        ok = proc.returncode == 0
        tail = (proc.stdout.strip().splitlines() or [""])[-1]
        print("%s  %-20s %5.1fs  %s" % ("ok  " if ok else "FAIL", script,
                                        time.time() - t, tail[:70]))
        if not ok:
            failed.append(script)
            # The failing lines, so nobody has to rerun it to see why.
            for line in proc.stdout.splitlines():
                if line.startswith("[FAIL]") or "CRASH" in line or line.startswith("  -"):
                    print("        " + line)
            if proc.stderr.strip():
                print("        " + proc.stderr.strip().splitlines()[-1])

    print()
    print("%d of %d passed in %.1fs" % (len(wanted) - len(failed), len(wanted),
                                        time.time() - started))
    if failed:
        print("failed:", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
