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
    "test_card_text.py",   # every card's text, filled from its own numbers
    "test_plugin.py",      # the optional server plugin: absent, present, failing
    "test_combat_log.py",  # every action and outcome logged; the fight replays from it
    "test_legal_actions.py",  # every listed action accepted, every other refused
    "test_wait.py",        # waiting never stalls a round; the agent's fixed action menu
    "test_rng_streams.py", # one seeded stream per purpose; the global random untouched
    "test_card_groups.py", # the agent plugin: card groups and descriptors
    "test_analyzer.py",    # the Characteristic Analyzer: arithmetic, and through the session
    "test_turn_export.py", # a log's raw lines as turns; aura turns rebuilt by a replay
    "test_teammates.py",   # five scripted teammates, and the analyzer reading their styles
    "test_ironclad_game.py",  # Ironclad behaviour as the installed game's code has it
    "test_colorless_game.py",  # colorless, event, status and curse cards as the game's code has them
    "test_enemies.py",     # scripted enemies, the bosses, the Act 1 pool
    "test_overgrowth.py",  # the Overgrowth enemies ported since: Inklet, Fogmog, ...
    "test_underdocks.py",  # the Underdocks enemies: Seapunk, Sewer Clam, ...
    "test_scaling.py",     # every enemy at 1-4 players: what scales, what must not
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
