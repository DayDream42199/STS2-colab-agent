"""The Characteristic Analyzer's input, out of a combat log, per teammate.

Each scored turn is an "analyzer_input" line in the log (aura.py writes it at
round end): energy, hand, used, opp, incoming, block. This writes them out in
the MockUpRB prototype's shape - one list per teammate, a turn per entry:

    [E_total, Used, Opp, D, B]        each card [cost, dmg, block, groups]

The first four are the prototype's own; B, the Block they had when they ended
the turn, is added at the end - its I needs it.

    python -m Plugins.history_export <combat log> [folder]      (from Server/)

writes <log name>_<unit id>.json per teammate, next to the log or into folder.
Read one back with json.load: it is the prototype's turnData.
"""
import json
import os
import sys


def turns_by_player(lines):
    """The analyzer's input from a log's lines: {unit_id: [turn, ...]}, each
    turn the dict aura.py logged, in the order played."""
    out = {}
    for line in lines:
        if line.get("event") == "analyzer_input":
            turn = {k: v for k, v in line.items() if k not in ("seq", "time", "event", "unit_id")}
            out.setdefault(line["unit_id"], []).append(turn)
    return out


def prototype_turn(turn):
    """One turn in the prototype's list format."""
    card = lambda c: [c["cost"], c["dmg"], c["block"], list(c["groups"])]
    return [turn["energy"], [card(c) for c in turn["used"]], [card(c) for c in turn["opp"]],
            turn["incoming"], turn["block"]]


def export(log_path, folder=None):
    """Write each teammate's turns; returns the files written."""
    from combat_log import read
    folder = folder or os.path.dirname(os.path.abspath(log_path))
    base = os.path.splitext(os.path.basename(log_path))[0]
    written = []
    for unit_id, turns in turns_by_player(read(log_path)).items():
        path = os.path.join(folder, "%s_%s.json" % (base, unit_id))
        with open(path, "w", encoding="utf-8") as handle:
            json.dump([prototype_turn(t) for t in turns], handle)
        written.append((path, len(turns)))
    return written


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    files = export(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    if not files:
        print("No analyzer_input lines in that log (was the aura plugin on, and did a round end?).")
    for path, count in files:
        print("%s: %d turns" % (path, count))
