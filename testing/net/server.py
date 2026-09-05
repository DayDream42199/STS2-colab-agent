# -*- coding: utf-8 -*-
"""Authoritative combat server."""

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.abspath(__file__)))))


import queue
import socket
import threading

from game_engine.entities import seed_content
from testing import config
from testing.net import games, protocol as P


class ClientLink(object):
    """One connected player: a socket and a reader thread."""

    def __init__(self, sock, addr, seat, sink):
        self.sock = sock
        self.addr = addr
        self.seat = seat
        self.sink = sink
        self.name = "Hero {}".format(seat + 1)
        self.wants_obs = False
        self.alive = True
        self.thread = threading.Thread(target=self._read_loop, daemon=True)

    def start(self):
        self.thread.start()

    def _read_loop(self):
        try:
            for msg in P.LineReader(self.sock).messages():
                self.sink.put((self, msg))
        except P.Disconnected:
            pass
        finally:
            self.alive = False
            self.sink.put((self, {"type": "quit", "reason": "disconnected"}))

    def send(self, obj):
        if not self.alive:
            return
        try:
            P.send(self.sock, obj)
        except P.Disconnected:
            self.alive = False

    def close(self):
        self.alive = False
        try:
            self.sock.close()
        except OSError:
            pass


class Server(object):
    def __init__(self, host="127.0.0.1", port=P.PORT, players=None,
                 config_path=None, seed=None, kind="full"):
        self.cfg = config.load(config_path, quiet=True)
        self.kind = kind
        if players:
            self.n_players = players
        elif kind == "simple":
            self.n_players = config.simple_kwargs(self.cfg)["players"]
        else:
            self.n_players = max(1, len(self.cfg["party"]))
        self.host, self.port = host, port
        self.seed = seed if seed is not None else self.cfg.get("seed")
        self.links = []
        self.events = queue.Queue()
        self.ended = set()      # seats done for this round
        self.game = None

    def accept_clients(self):
        srv = P.listening_socket(self.host, self.port)
        print("listening on {}:{} -- waiting for {} player(s)".format(
            self.host, self.port, self.n_players))
        print("  clients: python testing/net/client.py --port {}".format(self.port))
        try:
            while len(self.links) < self.n_players:
                sock, addr = srv.accept()
                link = ClientLink(sock, addr, len(self.links), self.events)
                try:
                    first = next(P.LineReader(sock).messages())
                except P.Disconnected:
                    sock.close()
                    continue
                if first.get("type") != "join":
                    P.send(sock, {"type": "error", "text": "expected join"})
                    sock.close()
                    continue
                link.name = str(first.get("name") or link.name)[:24]
                link.wants_obs = bool(first.get("wants_obs"))
                link.start()
                self.links.append(link)
                print("  seat {}: {} from {}".format(
                    link.seat, link.name, addr[0]))
                self.broadcast({"type": "log", "lines": [
                    "{} joined ({}/{})".format(link.name, len(self.links),
                                               self.n_players)]})
        finally:
            srv.close()

    def broadcast(self, obj):
        for link in self.links:
            link.send(obj)

    def push_state(self):
        for link in self.links:
            link.send(P.view_for(self.game, link.seat,
                                 your_turn=self.can_act(link.seat),
                                 with_obs=link.wants_obs))

    def can_act(self, seat):
        """Anyone still in the round may act, in any order."""
        engine = self.game.engine
        if engine.is_over or seat in self.ended:
            return False
        return seat < len(engine.players) and engine.players[seat].alive

    def _live_seats(self):
        return {i for i in range(len(self.links)) if self.can_act(i)}

    def end_round(self):
        """Enemy phase, then a fresh round with everyone able to act again."""
        self.game.end_round()
        self.ended.clear()

    def run(self):
        self.accept_clients()
        if self.seed is not None:
            seed_content(self.seed)
        self.game = games.build(self.kind, self.cfg, self.n_players, self.seed)
        self.game.reset()
        engine = self.game.engine
        for i, link in enumerate(self.links):
            if i < len(engine.players):
                engine.players[i].name = link.name
            link.send({"type": "welcome", "seat": link.seat,
                       "of": self.n_players, "game": self.game.name,
                       "action_space": self.game.action_space})
        print("{} fight started: {} vs {}".format(
            self.game.name,
            ", ".join(p.name for p in engine.players),
            ", ".join(e.name for e in engine.enemies)))

        log_seen = 0
        self.push_state()
        while not self.game.engine.is_over:
            if not self._live_seats():
                self.end_round()
                self.push_state()
                continue

            link, msg = self.events.get()

            if msg.get("type") == "quit":
                print("  {} left -- ending the fight".format(link.name))
                self.broadcast({"type": "log",
                                "lines": ["{} left".format(link.name)]})
                break
            if msg.get("type") != "action":
                link.send({"type": "error", "text": "expected an action"})
                continue

            refusal = self._refuse(link, msg.get("id"))
            if refusal is not None:
                link.send({"type": "error", "text": refusal})
                continue

            action = int(msg["id"])
            if action == self.game.end_turn_id:
                self.ended.add(link.seat)
                self.broadcast({"type": "log",
                                "lines": ["{} ends their turn".format(link.name)]})
            else:
                self.game.apply(link.seat, action)

            new_log = self.game.engine.log[log_seen:]
            log_seen = len(self.game.engine.log)
            if new_log:
                self.broadcast({"type": "log", "lines": new_log})
            self.push_state()

        engine = self.game.engine
        self.broadcast({"type": "over",
                        "victory": bool(engine.victory),
                        "turns": engine.turn_number,
                        "lines": engine.log[log_seen:]})
        print("fight over: {}".format("VICTORY" if engine.victory else "DEFEAT"))
        for link in self.links:
            link.close()

    def _refuse(self, link, action):
        """Why this action is rejected, or None to allow it."""
        if link.seat in self.ended:
            return "you have already ended your turn this round"
        if not self.can_act(link.seat):
            return "you cannot act right now"
        if not isinstance(action, int) or isinstance(action, bool):
            return "action id must be an integer"
        if not 0 <= action < self.game.action_space:
            return "action {} is outside 0..{}".format(
                action, self.game.action_space - 1)
        # The mask is per-player, so ask it as the sender.
        if not self.game.legal_mask(seat=link.seat)[action]:
            return "action {} ({}) is not legal right now".format(
                action, self.game.label_for(link.seat, action))
        return None


def _arg(argv, flag, default=None, cast=str):
    if flag in argv:
        return cast(argv[argv.index(flag) + 1])
    return default


def main():
    argv = _sys.argv[1:]
    Server(host=_arg(argv, "--host", "127.0.0.1"),
           port=_arg(argv, "--port", P.PORT, int),
           players=_arg(argv, "--players", None, int),
           seed=_arg(argv, "--seed", None, int),
           kind="simple" if "--simple" in argv else "full").run()


if __name__ == "__main__":
    main()
