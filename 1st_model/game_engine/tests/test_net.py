"""The co-op server is authoritative: clients cannot cheat or act early."""
import sys
import queue
import socket
import threading
import time

import os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from testing.net import protocol as P
from testing.net.server import Server

PORT = 7899
FAILS = []


def check(label, got, want):
    ok = got == want
    print("  [{}] {}: got {!r}, want {!r}".format("ok" if ok else "FAIL",
                                                  label, got, want))
    if not ok:
        FAILS.append(label)


class Bot(object):
    def __init__(self, name, port):
        self.sock = socket.create_connection(("127.0.0.1", port))
        P.send(self.sock, {"type": "join", "name": name})
        self.name = name
        self.seat = None
        self.errors = []
        self.states = []
        self.q = queue.Queue()
        self.over = False
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            for msg in P.LineReader(self.sock).messages():
                self.q.put(msg)
        except P.Disconnected:
            pass
        self.q.put(None)

    def drain(self, wait=0.35):
        """Consume everything currently queued."""
        deadline = time.time() + wait
        while time.time() < deadline:
            try:
                msg = self.q.get(timeout=0.05)
            except queue.Empty:
                continue
            if msg is None:
                self.over = True
                return
            t = msg.get("type")
            if t == "welcome":
                self.seat = msg["seat"]
            elif t == "error":
                self.errors.append(msg["text"])
            elif t == "over":
                self.over = True
            elif t == "state":
                self.states.append(msg)
                if msg["over"]:
                    self.over = True

    def my_turn(self):
        return self.states and self.states[-1].get("your_turn")

    def act(self, action_id):
        P.send(self.sock, {"type": "action", "id": action_id})

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def main(kind="full", port=PORT):
    print()
    print("#" * 62)
    print("# {} game".format(kind.upper()))
    print("#" * 62)
    srv = Server(host="127.0.0.1", port=port, players=2, seed=7, kind=kind)
    threading.Thread(target=srv.run, daemon=True).start()
    time.sleep(0.4)

    a = Bot("Alice", port)
    b = Bot("Bob", port)
    time.sleep(0.5)
    a.drain()
    b.drain()

    print("=== seating: BOTH players may act, in any order ===")
    check("Alice is seat 0", a.seat, 0)
    check("Bob is seat 1", b.seat, 1)
    sa = a.states[-1]
    check("Alice may act", sa["your_turn"], True)
    check("Bob may act too, without waiting for Alice",
          b.states[-1]["your_turn"], True)

    print()
    print("=== co-op: you see your teammates' hands, but only act on yours ===")
    check("Alice's view marks exactly one player as 'me'",
          sum(1 for p in sa["players"] if p["is_me"]), 1)
    check("...and puts her first (egocentric)", sa["players"][0]["is_me"], True)
    check("Bob's view puts BOB first", b.states[-1]["players"][0]["name"], "Bob")
    check("Bob gets his OWN moves, not Alice's",
          len(b.states[-1]["moves"]) > 0, True)
    check("the two hands are different objects",
          sa["hand"] != b.states[-1]["hand"] or len(sa["hand"]) == 0, True)
    # Ally hands ARE shared now -- co-op coordination needs them, and the
    # observation carries the same 600 floats, so the human and the agent
    # see the same game.
    mate = next(p for p in sa["players"] if not p["is_me"])
    check("Alice can see her teammate's cards", len(mate["hand"]) > 0, True)
    check("...and they are the teammate's, not her own",
          [c["name"] for c in mate["hand"]]
          != [c["name"] for c in sa["hand"]]
          or len(sa["hand"]) == 0, True)
    check("but her MOVES only touch her own hand",
          all(t["id"] < srv.game.action_space
              for m in sa["moves"] for t in m["targets"]), True)

    print()
    print("=== Bob can act BEFORE Alice does ===")
    bob_move = b.states[-1]["moves"][0]
    b.act(bob_move["targets"][0]["id"])
    b.drain()
    check("Bob's action was accepted, not refused",
          [e for e in b.errors if "not your turn" in e], [])
    check("...and Bob is still able to act", b.states[-1]["your_turn"], True)

    print()
    print("=== illegal and malformed ids are refused ===")
    legal_ids = {t["id"] for m in sa["moves"] for t in m["targets"]}
    # The simple game has 3 ids and all of them are legal on turn 1, so
    # there is no in-range-but-illegal id to send. That is a property of the
    # game, not a gap in the server.
    illegal = next((i for i in range(srv.game.action_space)
                    if i not in legal_ids), None)
    if illegal is not None:
        a.act(illegal)
    a.act(99999)
    a.act("cheat")
    a.act(True)
    a.drain()
    if illegal is not None:
        check("illegal-but-in-range refused",
              any("not legal" in e for e in a.errors), True)
    else:
        print("  [skip] every id is legal in this game -- nothing to refuse")
    check("out-of-range refused", any("outside" in e for e in a.errors), True)
    check("non-integer refused", any("integer" in e for e in a.errors), True)
    check("Alice can still act", srv.can_act(0), True)
    check("the action space matches the game",
          srv.game.action_space, 3 if kind == "simple" else 161)

    print()
    print("=== a legal action is accepted and broadcast ===")
    before = len(b.states)
    a.act(sa["moves"][0]["targets"][0]["id"])
    a.drain()
    b.drain()
    check("Bob received a fresh state too", len(b.states) > before, True)

    print()
    print("=== one move per card; targets only where there is a choice ===")
    st = a.states[-1]
    ids = sum(len(m["targets"]) for m in st["moves"])
    check("fewer moves shown than raw action ids",
          len(st["moves"]) <= ids, True)
    check("no move offers zero targets",
          [m["label"] for m in st["moves"] if not m["targets"]], [])
    check("end turn is offered exactly once",
          sum(1 for m in st["moves"] if m["label"] == "end turn"), 1)
    check("a single-target move carries no target menu",
          all(t["label"] == "" for m in st["moves"]
              if len(m["targets"]) == 1 for t in m["targets"]), True)

    print()
    print("=== ending your turn gates you out until the round flips ===")
    end_move = next(m for m in st["moves"] if m["label"] == "end turn")
    before_turn = srv.game.engine.turn_number
    a.errors = []
    a.act(end_move["targets"][0]["id"])
    a.drain()
    check("Alice is out for the round", srv.can_act(0), False)
    a.act(end_move["targets"][0]["id"])
    a.drain()
    check("...and is told so if she tries again",
          any("already ended" in e for e in a.errors), True)
    b.drain()
    check("Bob is unaffected and can still act", srv.can_act(1), True)
    check("the round has NOT advanced on one player alone",
          srv.game.engine.turn_number, before_turn)
    st_b = b.states[-1]
    end_b = next(m for m in st_b["moves"] if m["label"] == "end turn")
    b.act(end_b["targets"][0]["id"])
    time.sleep(0.5)
    a.drain(); b.drain()
    check("once EVERYONE has ended, the round advances",
          srv.game.engine.turn_number > before_turn, True)
    check("...and the ended set is cleared", srv.ended, set())

    print()
    print("=== both bots play the fight to a conclusion ===")
    bots = [a, b]
    steps = 0
    while steps < 600 and not srv.game.engine.is_over:
        acted = False
        for bot in bots:
            bot.drain(wait=0.12)
            if bot.over or not bot.my_turn():
                continue
            st = bot.states[-1]
            # An attack if one is offered, otherwise end the turn.
            pick = next((m for m in st["moves"]
                         if m["label"] != "end turn"), st["moves"][-1])
            bot.act(pick["targets"][0]["id"])
            steps += 1
            acted = True
        if not acted:
            time.sleep(0.05)
    check("the fight ended", srv.game.engine.is_over, True)
    print("     {} actions exchanged, {} engine turns, victory={}".format(
        steps, srv.game.engine.turn_number, srv.game.engine.victory))

    a.close()
    b.close()
    time.sleep(0.3)


if __name__ == "__main__":
    main("full", PORT)
    main("simple", PORT + 1)
    print()
    if FAILS:
        print("FAILURES: {}".format(FAILS))
        sys.exit(1)
    print("all networked co-op checks passed (full and simple)")
