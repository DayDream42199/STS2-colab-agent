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

A log written without the aura plugin has no such lines. load() then makes
them by replaying the fight from its seed with the plugin on (rebuild()),
and says how that went; ca_feed.py, ca_plot.py and turn_export.py load logs
the same way.
"""
import json
import os
import sys

# The moves a replay must make again for its turns to be the logged fight's.
MOVES = ("play", "choose", "end_turn", "wait", "left")


def turns_by_player(lines):
    """The analyzer's input from a log's lines: {unit_id: [turn, ...]}, each
    turn the dict aura.py logged, in the order played."""
    out = {}
    for line in lines:
        if line.get("event") == "analyzer_input":
            turn = {k: v for k, v in line.items() if k not in ("seq", "time", "event", "unit_id", "rebuilt")}
            out.setdefault(line["unit_id"], []).append(turn)
    return out


def load(log_path):
    """A log's lines with the aura plugin's turns in them: as logged, or for
    a log without any, rebuilt (and added at the end). Returns (lines, note):
    note is None when the log had its own, else what the rebuild says."""
    from combat_log import read
    lines = read(log_path)
    if any(line.get("event") == "analyzer_input" for line in lines):
        return lines, None
    try:
        rebuilt, note = rebuild(lines)
    except Exception as error:          # the log's own lines are still worth having
        return lines, "No aura lines in the log, and replaying it to make them failed: %s: %s" % (
            type(error).__name__, error)
    return lines + rebuilt, note


def _moves(lines):
    """(the turn it fell in, what was done) for each move, in order."""
    out, turn = [], 0
    for line in lines:
        if line["event"] == "turn_start":
            turn = line["turn"]
        elif line["event"] in MOVES:
            out.append((turn, [line["event"], line.get("unit_id"), line.get("card_id"), line.get("upgraded"),
                               line.get("target_id"), line.get("option")]))
    return out


def rebuild(lines):
    """The aura plugin's lines (analyzer_input, profile_update) for a logged
    fight, by playing it again from its seed with the plugin on. Each is
    marked "rebuilt" and has no seq. Returns (those lines, a note on the
    replay). They are kept only up to the first move that came out
    differently from the log (another card, or one refused), since past it the
    replay is another fight. The profiles are today's analyzer's, at its
    BETA now."""
    from combat_log import MemoryLog, replay
    from GameEngine.Combat.combat import Combat
    from plugin_host import PluginGuard
    from .analyzer import BETA
    from .aura import create_plugin

    log = MemoryLog()
    problems = replay(lines, Combat, plugin=PluginGuard(create_plugin(), "Plugins.aura"), log=log)
    if not log.lines:
        return [], "No aura lines in the log, and it cannot be replayed to make them: %s." % problems[0]
    logged, replayed = _moves(lines), _moves(log.lines)
    split = next((i for i, (a, b) in enumerate(zip(logged, replayed)) if a[1] != b[1]),
                 min(len(logged), len(replayed)))
    kept, moves = [], 0
    for line in log.lines:
        moves += line["event"] in MOVES
        if moves > split:
            break
        if line["event"] in ("analyzer_input", "profile_update"):
            kept.append(dict({k: v for k, v in line.items() if k != "seq"}, rebuilt=True))
    turns = sum(line["event"] == "analyzer_input" for line in kept)
    if split < len(logged):
        turn, (event, unit_id, card_id) = logged[split][0], logged[split][1][:3]
        return kept, ("No aura lines in the log, and replaying the fight with the plugin went differently "
                      "from turn %d (the log has %s %s%s there), so %s." % (
                          turn, unit_id, event, " " + card_id if card_id else "",
                          "only the %d scored turns before it were rebuilt (profiles at beta %s)"
                          % (turns, BETA) if turns else "no turn could be rebuilt"))
    if not turns:
        return kept, ("No aura lines in the log, and replaying it with the plugin scores no turn either: "
                      "no teammate's turn ran to the end of a round.")
    note = ("No aura lines in the log: rebuilt %d scored turns by replaying the fight with the plugin "
            "(profiles at beta %s)" % (turns, BETA))
    if problems:
        return kept, note + (". Every move replayed as logged, but the states are not the logged ones "
                             "(the cards or the state format changed since), so the numbers are "
                             "today's cards'.")
    return kept, note + ": every move and state as logged."


def prototype_turn(turn):
    """One turn in the prototype's list format."""
    card = lambda c: [c["cost"], c["dmg"], c["block"], list(c["groups"])]
    return [turn["energy"], [card(c) for c in turn["used"]], [card(c) for c in turn["opp"]],
            turn["incoming"], turn["block"]]


def export(log_path, folder=None, lines=None):
    """Write each teammate's turns; returns the files written. `lines`: the
    log's lines already loaded (load()), else they are loaded here."""
    if lines is None:
        lines, _ = load(log_path)
    folder = folder or os.path.dirname(os.path.abspath(log_path))
    base = os.path.splitext(os.path.basename(log_path))[0]
    written = []
    for unit_id, turns in turns_by_player(lines).items():
        path = os.path.join(folder, "%s_%s.json" % (base, unit_id))
        with open(path, "w", encoding="utf-8") as handle:
            json.dump([prototype_turn(t) for t in turns], handle)
        written.append((path, len(turns)))
    return written


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    lines, note = load(sys.argv[1])
    if note:
        print(note)
    files = export(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None, lines)
    if not files:
        print("No scored turns in that log: nothing to write.")
    for path, count in files:
        print("%s: %d turns" % (path, count))
