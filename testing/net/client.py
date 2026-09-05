# -*- coding: utf-8 -*-
"""Terminal client."""

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.abspath(__file__)))))


import queue
import socket
import threading

from testing.net import protocol as P


def bar(cur, mx, width=20):
    filled = 0 if mx <= 0 else max(0, min(width, round(width * cur / mx)))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def render(state):
    print()
    print("=" * 68)
    print("Turn {}".format(state["turn"]))
    print("-- Enemies --")
    for i, e in enumerate(state["enemies"]):
        if not e["alive"]:
            print("  {}: {}  (down)".format(i, e["name"]))
            continue
        intent = e["intent"]
        tag = ("{} ({} dmg)".format(intent["name"], intent["damage"])
               if intent else "-")
        st = "  ".join("{} {}".format(k, v) for k, v in e["statuses"].items())
        print("  {}: {:<22} {} {:>4}/{:<4} Intent: {}{}".format(
            i, e["name"], bar(e["hp"], e["max_hp"]), e["hp"], e["max_hp"],
            tag, "   [" + st + "]" if st else ""))

    print("-- Party --")
    for p in state["players"]:
        mark = "->" if p["is_me"] else "  "
        st = "  ".join("{} {}".format(k, v) for k, v in p["statuses"].items())
        print("{} {:<12} {} {:>3}/{:<3}  Block {:<3} Energy {}/{}{}".format(
            mark, p["name"], bar(p["hp"], p["max_hp"]), p["hp"], p["max_hp"],
            p["block"], p["energy"], p["max_energy"],
            "   [" + st + "]" if st else ""))
        if not p["is_me"] and p["hand"]:
            names = ", ".join("[{}] {}{}".format(c["cost"], c["name"],
                                                 "+" if c["upgraded"] else "")
                              for c in p["hand"])
            print("      holds: {}".format(names))

    if state["hand"]:
        print("-- Your hand --")
        for i, c in enumerate(state["hand"]):
            flag = " " if c["playable"] else "x"
            print("  {} {}: [{}] {:<20} {}".format(
                flag, i, c["cost"], c["name"] + ("+" if c["upgraded"] else ""),
                c["text"]))


def ask(prompt, n, sock):
    """An index in 0..n-1, or quit. None means 'go back'."""
    while True:
        try:
            raw = input(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            P.send(sock, {"type": "quit"})
            raise SystemExit(0)
        if raw in ("q", "quit"):
            P.send(sock, {"type": "quit"})
            raise SystemExit(0)
        if raw in ("b", "back"):
            return None
        if raw.isdigit() and int(raw) < n:
            return int(raw)
        print("  pick a number from the list, b to go back, or q to quit")


def choose(state, sock):
    """Pick a card, then a target only if the card has a choice to make."""
    moves = state["moves"]
    if not moves:
        return
    while True:
        print()
        print("-- Your move --")
        for i, mv in enumerate(moves):
            n = len(mv["targets"])
            tag = "  ({} targets)".format(n) if n > 1 else ""
            print("  {:>2}: {:<26} {}{}".format(i, mv["label"], mv["text"], tag))
        pick = ask("  card [0-{}]> ".format(len(moves) - 1), len(moves), sock)
        if pick is None:
            continue
        targets = moves[pick]["targets"]
        if len(targets) == 1:
            P.send(sock, {"type": "action", "id": targets[0]["id"]})
            return
        print()
        print("  -- {} at which? --".format(moves[pick]["label"]))
        for i, t in enumerate(targets):
            print("    {:>2}: {}".format(i, t["label"]))
        which = ask("  target [0-{}], b to pick another card> "
                    .format(len(targets) - 1), len(targets), sock)
        if which is None:
            continue
        P.send(sock, {"type": "action", "id": targets[which]["id"]})
        return


def reader(sock, inbox):
    try:
        for msg in P.LineReader(sock).messages():
            inbox.put(msg)
    except P.Disconnected:
        pass
    inbox.put(None)


def run(host, port, name):
    sock = socket.create_connection((host, port))
    P.send(sock, {"type": "join", "name": name})
    inbox = queue.Queue()
    threading.Thread(target=reader, args=(sock, inbox), daemon=True).start()
    print("connected to {}:{} as {}".format(host, port, name))

    while True:
        msg = inbox.get()
        if msg is None:
            print("\n  server closed the connection")
            return
        kind = msg.get("type")
        if kind == "welcome":
            print("  seated at {} of {} ({} actions in the space)".format(
                msg["seat"], msg["of"], msg["action_space"]))
        elif kind == "log":
            for line in msg["lines"]:
                print("    {}".format(line))
        elif kind == "error":
            print("  ! {}".format(msg["text"]))
        elif kind == "state":
            render(msg)
            if msg["over"]:
                continue
            if msg["your_turn"]:
                choose(msg, sock)
            else:
                print("\n  you are done this round -- waiting for the others")
        elif kind == "over":
            for line in msg.get("lines", []):
                print("    {}".format(line))
            print()
            print("=" * 68)
            print("  {} after {} turns".format(
                "VICTORY" if msg["victory"] else "DEFEAT", msg["turns"]))
            print("=" * 68)
            return


def _arg(argv, flag, default=None, cast=str):
    if flag in argv:
        return cast(argv[argv.index(flag) + 1])
    return default


def main():
    argv = _sys.argv[1:]
    try:
        run(host=_arg(argv, "--host", "127.0.0.1"),
            port=_arg(argv, "--port", P.PORT, int),
            name=_arg(argv, "--name", "Player"))
    except ConnectionRefusedError:
        print("no server there -- start it with "
              "`python testing/net/server.py` first")
    except KeyboardInterrupt:
        print("\n  (quit)")


if __name__ == "__main__":
    main()
