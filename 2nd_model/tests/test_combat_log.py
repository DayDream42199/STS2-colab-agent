"""The combat log: every action, decision and outcome on its own line, and a
fight that replays exactly from it."""
import json, os, random, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "..", "Server")
sys.path.insert(0, SERVER)

from session import Session
from combat_log import CombatLog, NullLog, read, replay
from plugin_host import PluginGuard
from Protocol.protocol import encode
from Protocol.enums import ClientMessage
from GameEngine.Combat.combat import Combat
from GameEngine.Registry.card_registry import create_card
from GameEngine.Cards._card_enums import TargetType

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))


def send(s, sid, kind, **payload):
    return s.handle(sid, encode(kind, **payload))


def drive(s, turns):
    """Play by the protocol only - nothing touched behind the session's back,
    or the replay could not follow. Each player plays what they can afford,
    answers questions with option 0, and ends their turn."""
    for _ in range(turns):
        for sid in list(s.players):
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
                index = playable[0]
                card = create_card(ally.hand[index])
                target = None
                if card.target_type is TargetType.ENEMY:
                    target = next(e.unit_id for e in s.combat.enemies if e.is_alive())
                elif card.target_type is TargetType.ALLY:
                    target = next((a.unit_id for a in s.combat.allies
                                   if a is not ally and a.is_alive()), None)
                send(s, sid, ClientMessage.PLAY_CARD, hand_index=index, target_id=target)
            if s.is_running() and ally.is_alive():
                send(s, sid, ClientMessage.END_TURN)
        if not s.is_running():
            return


class Profiler:
    """Stands in for the analyzer: writes a profile update into the log."""
    def on_round_end(self, s):
        s.log_event("profile_update", unit_id="p2", traits={"A": 0.25, "S": 0.0, "T": -0.5})


# --- a whole fight, logged -----------------------------------------------------
folder = tempfile.mkdtemp()
s = Session(Combat, required_players=2, seed=1234, combat_log=CombatLog(folder),
            plugin=PluginGuard(Profiler(), "profiler"))
s.ENEMY_TYPE_IDS = ("leafslimemedium",)           # a short fight that still lasts a few rounds
s.add_player("sid1")
s.add_player("sid2")
send(s, "sid1", ClientMessage.IDENTIFY, role="agent")
first = next(i for i, c in enumerate(s.combat.hand_costs(s.players["sid1"])) if c == 1)
send(s, "sid1", ClientMessage.PLAY_CARD, hand_index=first,
     target_id="e1" if create_card(s.players["sid1"].hand[first]).target_type is TargetType.ENEMY else None,
     decision={"probabilities": [0.7, 0.2, 0.1]})
send(s, "sid1", ClientMessage.PLAY_CARD, hand_index=99)
drive(s, 15)

files = os.listdir(folder)
check("one file for the fight, named with its seed",
      len(files) == 1 and files[0].startswith("combat_") and files[0].endswith("_1234.jsonl"), files)
path = os.path.join(folder, files[0])
lines = read(path)
check("every line is JSON, numbered 0, 1, 2... in order",
      [l["seq"] for l in lines] == list(range(len(lines))) and all("time" in l for l in lines),
      len(lines))
events = [l["event"] for l in lines]
check("it opens with both players joining, the setup, and turn 1",
      events[:4] == ["join", "join", "combat_start", "turn_start"], events[:6])

start = lines[2]
check("combat_start has what a replay needs: seed, act, enemies, each player's deck",
      start["seed"] == 1234 and start["enemy_types"] == ["leafslimemedium"]
      and len(start["players"]) == 2 and all(p["deck"] for p in start["players"])
      and start["plugin"] == "profiler" and "allies" in start["state"], {k: start[k] for k in ("seed", "act", "enemy_types", "plugin")})
check("identify is logged with the role", any(l["event"] == "identify" and l["role"] == "agent" for l in lines))

play = next(l for l in lines if l["event"] == "play")
check("a play: who, which card, where, at whom, its cost/damage/Block before, and what it did",
      play["unit_id"] == "p1" and play["role"] == "agent" and play["hand_index"] == first
      and play["cost"] == 1 and "damage" in play and "block" in play and play["energy"] == 3
      and play["results"], {k: play.get(k) for k in ("card_id", "cost", "damage", "block", "energy")})
check("the agent's decision rides along with its action",
      play.get("decision") == {"probabilities": [0.7, 0.2, 0.1]}, play.get("decision"))
refused = next((l for l in lines if l["event"] == "refused"), None)
check("a refused action is logged, with the reason",
      refused is not None and refused["unit_id"] == "p1" and "out of range" in refused["error"], refused)
check("turns are framed: end_turn, round_end, turn_start",
      "end_turn" in events and "round_end" in events and events.count("turn_start") >= 2,
      {e: events.count(e) for e in ("end_turn", "round_end", "turn_start")})
updates = [l for l in lines if l["event"] == "profile_update"]
check("a plugin's own lines (profile updates) land in the same log",
      updates and updates[0]["traits"]["T"] == -0.5, len(updates))
end = lines[-1]
check("the last line is the outcome, with the final state",
      end["event"] == "combat_end" and end["result"] == "VICTORY" and "allies" in end["state"],
      end["event"])

# --- replay --------------------------------------------------------------------
check("the fight replays exactly from the log", replay(lines, Combat) == [], replay(lines, Combat))
# A Strike the log says was played, taken out: the enemy's HP has to differ.
# (Not a swapped hand index - the card beside it can be another copy of the
# same card - and not a Defend, whose Block can go unused.)
dropped = next(l for l in lines if l["event"] == "play" and l["seq"] > play["seq"]
               and l["card_id"] == "strike")
tampered = [dict(l) for l in lines if l is not dropped]
check("change one recorded action and the replay says so",
      replay(tampered, Combat) != [], replay(tampered, Combat)[:2])

result = subprocess.run([sys.executable, "combat_log.py", path], cwd=SERVER,
                        capture_output=True, text=True)
check("python combat_log.py <file> replays it from the command line",
      result.returncode == 0 and "Replayed exactly" in result.stdout, result.stdout + result.stderr)

# --- a player leaving mid-fight ---------------------------------------------------
folder2 = tempfile.mkdtemp()
s = Session(Combat, required_players=2, seed=99, combat_log=CombatLog(folder2))
s.ENEMY_TYPE_IDS = ("leafslimemedium",)
s.add_player("sid1")
s.add_player("sid2")
drive(s, 2)
s.remove_player("sid2")
drive(s, 15)
lines2 = read(os.path.join(folder2, os.listdir(folder2)[0]))
check("a player leaving is logged", any(l["event"] == "left" and l["unit_id"] == "p2" for l in lines2))
check("and the fight still replays exactly", replay(lines2, Combat) == [], replay(lines2, Combat))

# --- without a log, and with one that cannot be written --------------------------
s = Session(Combat, required_players=2)
check("no log given: nothing is written", isinstance(s.log, NullLog))
check("a session with no seed given picks one, so its log could replay it",
      isinstance(s.seed, int), s.seed)

blocked = os.path.join(tempfile.mkdtemp(), "not_a_folder")
open(blocked, "w").close()                        # a file where the folder should be
s = Session(Combat, required_players=2, seed=5, combat_log=CombatLog(blocked))
s.ENEMY_TYPE_IDS = ("twigslimesmall",)
s.add_player("sid1")
s.add_player("sid2")
drive(s, 15)
check("a log that cannot be written: reported, and the fight goes on to its end",
      s.combat.is_over(), s.combat.result)

# --- an unexpected error: answered and logged, and the fight goes on --------------
from GameEngine.Cards.strike import Strike
folder3 = tempfile.mkdtemp()
s = Session(Combat, required_players=1, seed=7, combat_log=CombatLog(folder3))
s.ENEMY_TYPE_IDS = ("nibbit",)
s.add_player("sid1")
ally = s.players["sid1"]
index = next(i for i, c in enumerate(ally.hand) if str(c) == "strike")
real = Strike.get_effects
Strike.get_effects = lambda self, context: 1 / 0          # a bug in a card
try:
    out = send(s, "sid1", ClientMessage.PLAY_CARD, hand_index=index, target_id="e1")
finally:
    Strike.get_effects = real
kinds = [(to, m["type"]) for to, m in out]
check("a card that raises: the server is still up, the sender gets an error, everyone the state",
      ("sid1", "error") in kinds and (None, "state") in kinds
      and "ZeroDivisionError" in out[0][1]["payload"]["message"], kinds)
after = send(s, "sid1", ClientMessage.END_TURN)
check("and the fight goes on: the next message is handled",
      all(m["type"] != "error" for _, m in after), [m["type"] for _, m in after])
lines3 = read(os.path.join(folder3, os.listdir(folder3)[0]))
error = next((l for l in lines3 if l["event"] == "error"), None)
check("the error is in the log with its traceback",
      error is not None and error["unit_id"] == "p1" and "ZeroDivisionError" in error["traceback"],
      error and error["error"])

print()
print("%d checks failed" % len(bad))
for label in bad:
    print("   ", label)

import sys as _sys
_sys.exit(1 if bad else 0)
