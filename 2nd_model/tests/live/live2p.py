"""Two-player live co-op against a real server.

Uses python-socketio's client rather than driving engine.io by hand. The
hand-rolled version had to answer pings itself and guess how many polls a
message would take to arrive, and it lost its connection on any run longer
than the 25s ping interval - which made unrelated checks fail at random.
Needs: pip install python-socketio requests websocket-client
"""
import queue
import sys
import time

import socketio

URL = "http://127.0.0.1:5000"
notes = []


def check(label, cond, detail=""):
    if not cond:
        notes.append(label)
    print("[%s] %s%s" % ("PASS" if cond else "FAIL", label,
                         (" -> " + str(detail)) if detail else ""))


class Player:
    def __init__(self, name):
        self.name = name
        self.inbox = queue.Queue()
        self.sio = socketio.Client(reconnection=False)
        self.sio.on("message", self.inbox.put)
        self.sio.connect(URL, transports=["polling"], wait_timeout=10)

    def send(self, payload):
        self.sio.emit("message", payload)

    def drain(self, seconds=2.0):
        """Everything that arrives within `seconds` of the last message."""
        msgs, deadline = [], time.time() + seconds
        while time.time() < deadline:
            try:
                msgs.append(self.inbox.get(timeout=0.4))
                deadline = time.time() + 0.6   # keep listening after a hit
            except queue.Empty:
                pass
        return msgs

    def close(self):
        try:
            self.sio.disconnect()
        except Exception:
            pass


def find(msgs, kind):
    for m in msgs:
        if m.get("type") == kind:
            return m.get("payload")
    return None


p1 = p2 = None
try:
    # --- p1 joins: should be told to wait ----------------------------------
    p1 = Player("p1")
    m1 = p1.drain()
    check("p1 welcome", find(m1, "welcome") is not None, [m.get("type") for m in m1])
    check("p1 is p1", (find(m1, "welcome") or {}).get("unit_id") == "p1")
    check("lobby says 1/2", find(m1, "lobby") == {"players": 1, "required": 2},
          find(m1, "lobby"))
    check("no combat yet (REQUIRED_PLAYERS=2)", find(m1, "state") is None)

    # --- p2 joins: combat starts -------------------------------------------
    p2 = Player("p2")
    m2 = p2.drain()
    check("p2 welcome as p2", (find(m2, "welcome") or {}).get("unit_id") == "p2",
          find(m2, "welcome"))
    st = find(m2, "state")
    check("combat starts on 2nd join", st is not None,
          [m.get("type") for m in m2])
    combat = st["combat"]
    check("two allies present", len(combat["allies"]) == 2, len(combat["allies"]))
    check("phase PLAYER_TURN", combat["phase"] == "PLAYER_TURN", combat["phase"])
    p1.drain(1.0)

    hand = combat["allies"][0]["hand"]
    enemy = combat["enemies"][0]
    print("\n    p1 hand: %s" % hand)
    print("    enemy %s hp %s intent %s\n"
          % (enemy["unit_id"], enemy["current_hp"], enemy.get("intent")))

    # --- p1 plays an attack -------------------------------------------------
    idx = next((i for i, c in enumerate(hand) if c in ("strike", "bash")), 0)
    p1.send({"type": "play_card",
             "payload": {"hand_index": idx, "target_id": enemy["unit_id"]}})
    got = p1.drain(3.0)
    check("effects broadcast", find(got, "effects") is not None,
          [m.get("type") for m in got])
    check("damage dealt", (find(got, "effects") or {}).get("results"),
          find(got, "effects"))

    # --- readiness ----------------------------------------------------------
    p2.drain(1.0)
    p1.send({"type": "end_turn"})
    got = p1.drain(3.0)
    rc = find(got, "ready_changed")
    check("ready_changed waits on p2",
          rc is not None and rc.get("waiting_on") == ["p2"], rc)

    p2.send({"type": "end_turn"})
    got = p1.drain(4.0)
    check("turn advances once both ready", find(got, "state") is not None,
          [m.get("type") for m in got])
    st2 = find(got, "state")
    if st2:
        check("energy refreshed after turn",
              st2["combat"]["allies"][0]["energy"] == 3,
              st2["combat"]["allies"][0]["energy"])

    # --- junk input is rejected privately -----------------------------------
    p2.drain(0.5)
    p1.send({"type": "not_a_real_message"})
    got = p1.drain(3.0)
    check("junk rejected privately", find(got, "error") is not None,
          [m.get("type") for m in got])
    check("junk did not reach the other player",
          find(p2.drain(1.0), "error") is None)

finally:
    for p in (p1, p2):
        if p is not None:
            p.close()

print()
print("%d FAILURE(S): %s" % (len(notes), notes) if notes
      else "ALL LIVE 2-PLAYER CHECKS PASSED")
sys.exit(1 if notes else 0)

import sys as _sys
_sys.exit(1 if notes else 0)
