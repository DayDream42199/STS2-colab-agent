"""The combat log: every action, decision and outcome of a fight, written as
it happens, so the fight can be replayed, debugged and evaluated.

One file per combat in config.LOG_DIR, named combat_<date>_<time>_<seed>.jsonl:
one JSON object per line, flushed line by line, so a crash keeps everything
up to it. Every line has "seq" (0, 1, 2...), "time" and "event":

    join          unit_id, sid
    identify      unit_id, role
    combat_start  seed, act, scale_enemies, required_players, ally_type,
                  enemy_types, players [{unit_id, sid, role, deck}], plugin, state
    turn_start    turn, state
    play          unit_id, role, card_id, upgraded, hand_index, target_id,
                  cost / damage / block / energy as the card stood in hand,
                  legal_actions (what was open instead), results,
                  decision (whatever the client sent with it, if any)
    choose        unit_id, role, prompt, option_index, option, options,
                  legal_actions, results, decision
    end_turn      unit_id, role, turn, legal_actions, decision
    wait          unit_id, role, turn, legal_actions, decision
    round_end     turn
    refused       unit_id, role, message (as the client sent it), error
    error         entry, sid, unit_id, message, error, traceback - an
                  unexpected exception the session caught; the fight went on
                  from wherever it got to, so a replay stops matching here
    left          unit_id, results (their questions answered at random)
    combat_end    result, turn, state
    ...and whatever a plugin records with session.log_event(event, ...) -
    agent decisions, profile updates.

`state` is the player-format state at that moment, in game units.

Replay: `python combat_log.py <file>` (from Server/) rebuilds the fight from
the seed and the recorded actions and checks every turn's state and the end
against the log. It needs the same cards, enemies and decks as when it was
recorded; a different deck is reported first. replay() can also run with a
plugin and a MemoryLog, to see what that plugin would have logged
(Plugins/history_export.py rebuilds the aura plugin's turns that way).
"""
import datetime
import json
import os
import sys


class NullLog:
    """No log: nothing is written."""
    active = False
    path = None
    tag = None

    def write(self, event, **data):
        pass

    def close(self):
        pass


class CombatLog:
    """Writes one combat's log, opening the file at the first line."""
    active = True

    def __init__(self, folder):
        self.folder = folder
        self.tag = None          # the session puts its seed here, for the file name
        self.path = None
        self._file = None
        self._seq = 0
        self._broken = False
        self._closed = False

    def _open(self):
        os.makedirs(self.folder, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        name = "combat_%s_%s.jsonl" % (stamp, self.tag if self.tag is not None else "noseed")
        self.path = os.path.join(self.folder, name)
        self._file = open(self.path, "a", encoding="utf-8")

    def write(self, event, **data):
        """Append one line. A log that cannot be written is reported once and
        then left alone: the fight never stops for it."""
        if self._broken or self._closed:
            return                       # one combat, one file: nothing after the end
        line = {"seq": self._seq, "time": datetime.datetime.now().isoformat(timespec="milliseconds"),
                "event": event}
        line.update(data)
        try:
            if self._file is None:
                self._open()
            self._file.write(json.dumps(line, default=str) + "\n")
            self._file.flush()
        except OSError as error:
            self._broken = True
            print(f"[combat log] cannot write to {self.path or self.folder}: {error}; "
                  "the fight goes on without a log.")
            return
        self._seq += 1

    def close(self):
        self._closed = True
        if self._file is not None:
            self._file.close()
            self._file = None


class MemoryLog:
    """A log kept as a list of lines, not a file: what a replay writes when
    it is given one. Each line goes through JSON, as the file would hold it."""
    active = True
    path = None

    def __init__(self):
        self.tag = None
        self.lines = []
        self._closed = False

    def write(self, event, **data):
        if self._closed:
            return
        line = {"seq": len(self.lines), "event": event}
        line.update(data)
        self.lines.append(json.loads(json.dumps(line, default=str)))

    def close(self):
        self._closed = True


# --- replay -----------------------------------------------------------------

def read(path):
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _same(a, b):
    # Through JSON, so a CardRef and its id string compare equal.
    return json.loads(json.dumps(a, default=str)) == json.loads(json.dumps(b, default=str))


def replay(lines, combat_factory, plugin=None, log=None):
    """Play a logged fight again from its seed and actions. Returns a list of
    differences: empty means every turn's state and the outcome came out
    exactly as logged. With a plugin (plugin_host.PluginGuard) and a log
    (MemoryLog), the replay runs with that plugin on and writes its own log,
    plugin lines included."""
    from session import Session                       # here: session imports this module
    from Protocol.protocol import encode
    from Protocol.enums import ClientMessage

    start = next((l for l in lines if l["event"] == "combat_start"), None)
    if start is None:
        return ["no combat_start in the log"]
    if start.get("seed") is None:
        return ["the log has no seed (the session was given its own rng), so it cannot be replayed"]

    session = Session(combat_factory, required_players=start["required_players"], seed=start["seed"],
                      plugin=plugin, combat_log=log)
    session.ALLY_TYPE_ID = start["ally_type"]
    session.ENEMY_TYPE_IDS = tuple(start["enemy_types"])
    session.ACT = start["act"]
    session.SCALE_ENEMIES = start["scale_enemies"]

    differences = []
    turn_starts = iter(l for l in lines if l["event"] == "turn_start")
    reached = {"turn": 0, "decks_checked": False}

    def snapshot():
        return session._state_message()["payload"]["combat"]

    def act(sid, kind, **payload):
        session.handle(sid, encode(kind, **payload))

    def check():
        """After each replayed action: the decks once the fight exists, and
        the state each time a new turn has begun (an answer or a player
        leaving can finish a round too, not only an end turn)."""
        if session.combat is None:
            return
        if not reached["decks_checked"]:
            reached["decks_checked"] = True
            decks = {a.unit_id: [str(c) for c in a.deck] for a in session.combat.allies}
            for player in start["players"]:
                if decks.get(player["unit_id"]) != player["deck"]:
                    differences.append("%s's deck is not the one logged - the cards or decks "
                                       "changed since, so the replay cannot match" % player["unit_id"])
        if not session.is_running() or session.combat.turn_number == reached["turn"]:
            return
        reached["turn"] = session.combat.turn_number
        logged = next(turn_starts, None)
        if logged is None:
            differences.append("turn %d started but the log has no such turn" % reached["turn"])
        elif logged["turn"] != reached["turn"]:
            differences.append("the replay reached turn %d where the log has turn %s"
                               % (reached["turn"], logged["turn"]))
        elif not _same(snapshot(), logged["state"]):
            differences.append("turn %s starts differently" % logged["turn"])

    sid_of = {}
    for line in lines:
        event = line["event"]
        if event == "join":
            sid_of[line["unit_id"]] = line["sid"]
            session.add_player(line["sid"])
        elif event == "identify":
            act(sid_of[line["unit_id"]], ClientMessage.IDENTIFY, role=line["role"])
        elif event == "play":
            act(sid_of[line["unit_id"]], ClientMessage.PLAY_CARD,
                hand_index=line["hand_index"], target_id=line["target_id"])
        elif event == "choose":
            act(sid_of[line["unit_id"]], ClientMessage.CHOOSE, option_index=line["option_index"])
        elif event == "end_turn":
            act(sid_of[line["unit_id"]], ClientMessage.END_TURN)
        elif event == "wait":
            act(sid_of[line["unit_id"]], ClientMessage.WAIT)
        elif event == "left":
            session.remove_player(sid_of[line["unit_id"]])
        check()
        if event == "combat_end":
            if session.combat is None or not session.combat.is_over():
                differences.append("the log ends the fight (%s) but the replay is still going"
                                   % line["result"])
            elif session.combat.result.name != line["result"]:
                differences.append("logged %s, replayed %s" % (line["result"], session.combat.result.name))
            elif not _same(snapshot(), line["state"]):
                differences.append("the fight ends in a different state")
    return differences


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python combat_log.py <log file>   (run from Server/)")
        sys.exit(2)
    from GameEngine.Combat.combat import Combat
    found = replay(read(sys.argv[1]), Combat)
    if found:
        print("The replay differs from the log:")
        for line in found:
            print("  -", line)
        sys.exit(1)
    print("Replayed exactly: every turn and the outcome match the log.")
