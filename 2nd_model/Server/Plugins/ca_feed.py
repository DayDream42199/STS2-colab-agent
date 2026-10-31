"""A fight's analyzer input, fed to the teammate's Characteristic Analyzer
package (2nd_model/CharacteristicAnalyzer, `import CharacteristicAnalyzer as
CA`) one turn at a time, and its profile shown next to ours.

    python -m Plugins.ca_feed <combat log> [profile folder]     (from Server/)

The input is each "analyzer_input" line in the log, in the list shape CA
takes - [E_total, Used, Opp, D, B], each card [cost, dmg, block, groups] -
which history_export.py writes. Each teammate gets a fresh CA profile,
<log name>_<unit id>_ca.json, in the profile folder (default: next to the
log), reset every run. Printed per turn: CA's profile; ours worked out again
at CA's beta, which should be the same numbers; and ours as the fight logged
it, at whatever analyzer.BETA was then (8 before 2026-10-31, 20 since).
ca_plot.py draws CA's profile as charts. A log written without the aura
plugin has its turns rebuilt by a replay first (history_export.load); then
there is no "as logged".
"""
import os
import sys

from . import analyzer
from .history_export import load, prototype_turn, turns_by_player

PACKAGE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                                       "CharacteristicAnalyzer"))
KEYS = ("A", "S", "T", "cA", "cS", "cT")


def load_ca():
    # The folder holding the package, at the end of the path: it holds the
    # rest of 2nd_model too, and nothing there should hide a Server module.
    if os.path.dirname(PACKAGE) not in sys.path:
        sys.path.append(os.path.dirname(PACKAGE))
    import CharacteristicAnalyzer as CA
    from CharacteristicAnalyzer.Internals import CharacteristicUpdate
    return CA, CharacteristicUpdate.beta


def feed(log_path, folder=None):
    """{unit_id: [(turn number, CA's profile, ours at CA's beta, ours as
    logged), ...]}, and CA's beta."""
    CA, beta = load_ca()
    lines, note = load(log_path)
    if note:
        print(note)
    CA.setProfileDir(folder or os.path.dirname(os.path.abspath(log_path)))
    base = os.path.splitext(os.path.basename(log_path))[0]
    logged = {(l["unit_id"], l["turn"]): l["profile"] for l in lines
              if l.get("event") == "profile_update" and not l.get("rebuilt")}
    out = {}
    for unit_id, turns in turns_by_player(lines).items():
        CA.newProfile(unit_id, "%s_%s_ca" % (base, unit_id), overwrite=True)
        ours = analyzer.new_profile()
        rows = out.setdefault(unit_id, [])
        for turn in turns:
            theirs = CA.updateProfile(unit_id, prototype_turn(turn))
            theirs = {k.replace("_", ""): v for k, v in theirs.items()}       # c_A -> cA
            analyzer.update(ours, analyzer.evidence(turn)[0], beta=beta)
            rows.append((turn["turn"], theirs, analyzer.values(ours), logged.get((unit_id, turn["turn"]))))
    return out, beta


def _row(profile):
    if profile is None:
        return "-"
    return "  ".join("%s %+.2f" % (k, profile[k]) for k in KEYS)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    found, beta = feed(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    if not found:
        sys.exit("No scored turns in that log.")
    for unit_id, rows in found.items():
        print("\n%s - %d turns" % (unit_id, len(rows)))
        for number, theirs, same_beta, logged in rows:
            print("  turn %d" % number)
            print("    CA (beta %d)     %s" % (beta, _row(theirs)))
            print("    ours (beta %d)   %s" % (beta, _row(same_beta)))
            print("    ours as logged   %s" % _row(logged))
        gap = max(abs(theirs[k] - same_beta[k]) for _, theirs, same_beta, _ in rows for k in KEYS)
        print("  CA and ours at the same beta: largest difference %.2g%s"
              % (gap, " - they agree" if gap < 1e-9 else " - THEY DISAGREE"))
