"""A combat log's raw lines as turns (Server/Plugins/turn_export.py), and the
aura plugin's turns rebuilt by a replay for a log written without it
(history_export.load / rebuild)."""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "..", "Server")
sys.path.insert(0, SERVER)

from session import Session
from combat_log import CombatLog, read
from plugin_host import PluginGuard
from Protocol.protocol import encode
from Protocol.enums import ClientMessage
from GameEngine.Combat.combat import Combat
from GameEngine.Registry.card_registry import create_card
from GameEngine.Cards._card_enums import TargetType
from Plugins.aura import create_plugin
from Plugins.history_export import export, load, rebuild
from Plugins.turn_export import MOVES, show, turns

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))


def send(s, sid, kind, **payload):
    return s.handle(sid, encode(kind, **payload))


def fight(with_aura):
    """One fight by the protocol only, so a replay can follow it: a refused
    play, a wait and a Defend sent with a target it does not take, then each
    player plays what they can afford and ends. Returns the log's path."""
    folder = tempfile.mkdtemp()
    s = Session(Combat, required_players=2, seed=77, combat_log=CombatLog(folder),
                plugin=PluginGuard(create_plugin(), "aura") if with_aura else None)
    s.ENEMY_TYPE_IDS = ("leafslimemedium",)
    s.add_player("a")
    s.add_player("b")
    send(s, "b", ClientMessage.PLAY_CARD, hand_index=99, target_id=None)       # refused
    send(s, "a", ClientMessage.WAIT)
    hand = [str(c) for c in s.players["b"].hand]
    if "defend" in hand:
        send(s, "b", ClientMessage.PLAY_CARD, hand_index=hand.index("defend"), target_id="e1")
    for _ in range(6):
        for sid in ("b", "a"):
            ally = s.players[sid]
            for _attempt in range(10):
                if not s.is_running() or not ally.is_alive():
                    break
                if s.combat.choice_for(ally) is not None:
                    send(s, sid, ClientMessage.CHOOSE, option_index=0)
                    continue
                costs = s.combat.hand_costs(ally)
                playable = [i for i, c in enumerate(costs) if isinstance(c, int) and c <= ally.energy]
                if not playable:
                    break
                card = create_card(ally.hand[playable[0]])
                target = (next(e.unit_id for e in s.combat.enemies if e.is_alive())
                          if card.target_type is TargetType.ENEMY else None)
                send(s, sid, ClientMessage.PLAY_CARD, hand_index=playable[0], target_id=target)
            if s.is_running() and ally.is_alive():
                send(s, sid, ClientMessage.END_TURN)
        if not s.is_running():
            break
    return os.path.join(folder, os.listdir(folder)[0])


strip = lambda line: {k: v for k, v in line.items() if k not in ("seq", "time", "rebuilt")}

print("== the raw lines as turns ==")
plain = fight(with_aura=False)
lines = read(plain)
fought = turns(lines)
starts = [l for l in lines if l["event"] == "turn_start"]
check("one entry per turn begun, in order, each with the state it began with",
      [t["turn"] for t in fought["turns"]] == [l["turn"] for l in starts] and len(starts) >= 3
      and all(t["state"] == l["state"] for t, l in zip(fought["turns"], starts)), len(starts))
check("every player in every turn, moves or not",
      all(set(t["players"]) == {"p1", "p2"} for t in fought["turns"]))
logged_moves = [l for l in lines if l["event"] in MOVES]
grouped = [(u, m) for t in fought["turns"] for u, p in t["players"].items() for m in p["moves"]]
check("every move once, under its player, nothing dropped",
      sorted(m["seq"] for _, m in grouped) == [l["seq"] for l in logged_moves]
      and all(u == l["unit_id"] for u, m in grouped for l in logged_moves if l["seq"] == m["seq"]),
      (len(grouped), len(logged_moves)))
check("each player's moves in the order made",
      all([m["seq"] for m in p["moves"]] == sorted(m["seq"] for m in p["moves"])
          for t in fought["turns"] for p in t["players"].values()))
first = fought["turns"][0]["players"]
check("the refused play and the wait are there, in turn 1",
      [m["move"] for m in first["p2"]["moves"]][:2] == ["refused", "play"]
      and first["p1"]["moves"][0]["move"] == "wait",
      ([m["move"] for m in first["p2"]["moves"]], [m["move"] for m in first["p1"]["moves"]]))
line = next(l for l in lines if l["event"] == "play")
move = next(m for _, m in grouped if m["seq"] == line["seq"])
check("a move is its log line, less time, unit_id and role",
      move == dict({k: v for k, v in line.items() if k not in ("event", "time", "unit_id", "role")},
                   move="play"), sorted(move))
end = next(l for l in lines if l["event"] == "combat_end")
check("the result and the end state from combat_end",
      fought["result"] == end["result"] and fought["end_state"] == end["state"], fought["result"])
check("no aura lines: no aura turns", fought["aura"] is None
      and all(p["analyzer_input"] is None for t in fought["turns"] for p in t["players"].values()))
text = show(fought)
stray = first["p2"]["moves"][1]
check("as text: a turn per heading, the Defend sent at e1 shown without a target",
      text.count("\nTurn ") == len(fought["turns"]) and "#%-4s Defend " % stray["seq"] in text
      and "Defend -> e1" not in text and "refused:" in text and "wait" in text,
      text.splitlines()[3:8])

print("\n== the aura turns, rebuilt by a replay ==")
with_aura = fight(with_aura=True)
aura_lines = [l for l in read(with_aura) if l["event"] in ("analyzer_input", "profile_update")]
check("the same fight with the plugin on scores turns", len(aura_lines) >= 4, len(aura_lines))
loaded, note = load(plain)
rebuilt = [l for l in loaded if l.get("rebuilt")]
check("a log without them gets them from a replay, and says it went exactly",
      "every move and state as logged" in note and len(rebuilt) == len(aura_lines), note)
check("the very lines the plugin logged in the fight itself",
      [strip(l) for l in rebuilt] == [strip(l) for l in aura_lines])
check("a log with them is left as it is", load(with_aura) == (read(with_aura), None))
fought = turns(loaded)
scored = [(t["turn"], u) for t in fought["turns"] for u, p in t["players"].items() if p["analyzer_input"]]
check("as turns: each scored turn under its player, marked rebuilt",
      fought["aura"] == "rebuilt"
      and scored == [(l["turn"], l["unit_id"]) for l in rebuilt if l["event"] == "analyzer_input"]
      and "aura: " in show(fought), scored)

# A move the replay cannot make again (a hand index nobody had): past it the
# replay is another fight, so only the turns before it are kept.
lines = read(plain)
turn = 0
for line in lines:
    turn = line["turn"] if line["event"] == "turn_start" else turn
    if turn == 3 and line["event"] == "play":
        line["hand_index"] = 99
        break
kept, note = rebuild(lines)
check("a replay that goes differently keeps only the turns before it",
      "differently from turn 3" in note and kept and all(l["turn"] < 3 for l in kept)
      and [strip(l) for l in kept] == [strip(l) for l in aura_lines if l["turn"] < 3], note)
lines =[l for l in read(plain) if l["event"] != "combat_start"]
kept, note = rebuild(lines)
check("a log with no combat_start: nothing rebuilt, and why", kept == [] and "cannot be replayed" in note, note)

print("\n== from the command line, from Server/ ==")
out = os.path.join(tempfile.mkdtemp(), "turns.json")
result = subprocess.run([sys.executable, "-m", "Plugins.turn_export", plain, out],
                        cwd=SERVER, capture_output=True, text=True)
check("python -m Plugins.turn_export <log> prints the turns and writes them",
      result.returncode == 0 and "Turn 1" in result.stdout and "aura turns: rebuilt" in result.stdout
      and json.load(open(out, encoding="utf-8")) == json.loads(json.dumps(turns(load(plain)[0]))),
      result.stdout[-300:] + result.stderr)
folder = tempfile.mkdtemp()
written = export(plain, folder)
check("history_export writes the rebuilt turns for a log without them",
      sorted(n for _, n in written) == sorted(
          sum(1 for l in aura_lines if l["event"] == "analyzer_input" and l["unit_id"] == u) for u in ("p1", "p2")),
      written)

from Plugins import ca_feed
if os.path.isdir(ca_feed.PACKAGE):
    found, _ = ca_feed.feed(plain, tempfile.mkdtemp())
    check("CA is fed the rebuilt turns, and nothing is shown as logged",
          set(found) == {"p1", "p2"} and all(row[3] is None for rows in found.values() for row in rows),
          {u: len(r) for u, r in found.items()})
else:
    print("[SKIP] the CharacteristicAnalyzer package is not here")

print()
if bad:
    print("FAILED: %d" % len(bad))
    for l in bad:
        print("  -", l)
    sys.exit(1)
print("ALL TURN EXPORT CHECKS PASSED")
