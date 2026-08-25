# -*- coding: utf-8 -*-
"""Run every suite. One command instead of a hand-typed 16-item shell loop.

    python tests/run_all.py            # everything
    python tests/run_all.py env choice # just the suites whose name contains these
    python tests/run_all.py -v         # stream each suite's own output

Each suite is a standalone script that prints its own [ok]/[FAIL] lines and
exits non-zero on failure, so this runs them as subprocesses and reports the
exit codes. That keeps them individually runnable and readable -- the point
of the format is that a failing check tells you what it expected, in game
terms, without a test framework in the way.

Exits non-zero if any suite fails, so it works as a pre-commit gate.
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

# Roughly fastest-first, and grouped: mechanics, then content, then the
# whole-game sweeps. smoke_all is last because it is much the slowest.
SUITES = [
    "test_thorns", "test_newcards", "test_powers", "test_relics",
    "test_potions", "test_choice", "test_handcap", "test_state_drift",
    "test_act1", "test_act2", "test_act3", "test_colorless", "test_env",
    "test_coop_view", "test_training_api", "test_deck_purity",
    "enemy_audit", "content_audit", "audit", "smoke_all",
]


def main(argv):
    verbose = "-v" in argv or "--verbose" in argv
    filters = [a for a in argv if not a.startswith("-")]
    suites = [s for s in SUITES
              if not filters or any(f in s for f in filters)]
    if not suites:
        print("no suite matches {!r}; known: {}".format(filters, ", ".join(SUITES)))
        return 2

    failed, t0 = [], time.time()
    for name in suites:
        path = os.path.join(HERE, name + ".py")
        sys.stdout.write("{:<16} ".format(name))
        sys.stdout.flush()
        started = time.time()
        proc = subprocess.run([sys.executable, path],
                              capture_output=not verbose, text=True)
        secs = time.time() - started
        if proc.returncode == 0:
            print("PASS  {:>5.1f}s".format(secs))
        else:
            print("FAIL  {:>5.1f}s".format(secs))
            failed.append((name, proc.stdout or "", proc.stderr or ""))

    print("-" * 40)
    print("{}/{} passed in {:.1f}s".format(
        len(suites) - len(failed), len(suites), time.time() - t0))

    # Show why, so a failure is actionable without re-running by hand.
    for name, out, err in failed:
        print("\n" + "=" * 60)
        print("FAILED: " + name)
        print("=" * 60)
        lines = [l for l in out.splitlines() if "[FAIL]" in l or "FAILURE" in l]
        print("\n".join(lines[-25:]) if lines else (out or "")[-2000:])
        if err.strip():
            print("--- stderr ---")
            print(err[-2000:])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
