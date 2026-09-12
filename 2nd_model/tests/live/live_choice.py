"""A real choice over a real socket: server asks, player clicks, card finishes.

Run against choice_server.py, whose ally deck is all Wish.
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
        msgs, deadline = [], time.time() + seconds
        while time.time() < deadline:
            try:
                msgs.append(self.inbox.get(timeout=0.4))
                deadline = time.time() + 0.6
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
    p1 = Player("p1")
    p1.drain(1.5)
    p2 = Player("p2")
    start = p2.drain(2.5)
    state = find(start, "state")
    check("combat started", state is not None)

    hand = state["combat"]["allies"][0]["hand"]
    check("p1 was dealt a hand of Wishes", "wish" in hand, hand)

    # --- play the card that asks -------------------------------------------
    p1.drain(0.5); p2.drain(0.5)
    p1.send({"type": "play_card", "payload": {"hand_index": hand.index("wish")}})
    mine = p1.drain(2.5)
    ask = find(mine, "choice_required")
    check("the server asks, over the wire", ask is not None,
          [m.get("type") for m in mine])
    check("the prompt says what is being asked", bool(ask and ask.get("prompt")),
          ask.get("prompt") if ask else None)
    check("and offers a list of card ids",
          bool(ask) and len(ask["options"]) > 0
          and all(isinstance(o, str) for o in ask["options"]),
          ask.get("options") if ask else None)

    state = find(mine, "state")
    check("the state broadcast shows the choice as pending",
          state and state["combat"]["choices"].get("p1") is not None,
          state["combat"]["choices"] if state else None)

    # --- the other player is told nothing private --------------------------
    theirs = p2.drain(1.0)
    check("the question itself did not go to the other player",
          find(theirs, "choice_required") is None,
          [m.get("type") for m in theirs])

    # --- answering finishes the card ---------------------------------------
    wanted = ask["options"][0]
    p1.drain(0.5)
    p1.send({"type": "choose", "payload": {"option_index": 0}})
    done = p1.drain(2.5)
    state = find(done, "state")
    check("answering clears the question",
          state and not state["combat"]["choices"],
          state["combat"]["choices"] if state else None)
    check("and the card the player picked is in their hand",
          state and wanted in state["combat"]["allies"][0]["hand"],
          (wanted, state["combat"]["allies"][0]["hand"] if state else None))

    # --- guards over the wire ----------------------------------------------
    p1.drain(0.5); p2.drain(0.5)
    p1.send({"type": "choose", "payload": {"option_index": 0}})
    check("answering with nothing pending is refused",
          find(p1.drain(1.5), "error") is not None)
    check("and privately", find(p2.drain(1.0), "error") is None)

    p1.drain(0.5)
    p1.send({"type": "choose", "payload": {"option_index": "banana"}})
    check("a non-integer answer is refused",
          find(p1.drain(1.5), "error") is not None)

finally:
    for player in (p1, p2):
        if player is not None:
            player.close()

print()
if notes:
    print("%d checks failed" % len(notes))
    for label in notes:
        print("   ", label)
else:
    print("ALL LIVE CHOICE CHECKS PASSED")

import sys as _sys
_sys.exit(1 if notes else 0)
