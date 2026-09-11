# -*- coding: utf-8 -*-
"""The wire protocol: framing, and the view each client is sent."""

import json
import socket

import game_engine.env as ENV
from game_engine.cards import TargetMode
from game_engine.observe import ALLY_FEATURE_NAMES, summarise_hand

PORT = 7801
ENCODING = "utf-8"


class Disconnected(Exception):
    """The peer closed the connection, cleanly or otherwise."""


def send(sock, obj):
    """One JSON object, one line."""
    try:
        sock.sendall((json.dumps(obj) + "\n").encode(ENCODING))
    except (OSError, BrokenPipeError) as exc:
        raise Disconnected(str(exc))


class LineReader(object):
    """Turns a socket's byte stream back into whole JSON messages."""

    def __init__(self, sock):
        self.sock = sock
        self.buf = b""

    def messages(self):
        """Yield decoded objects until the peer goes away."""
        while True:
            while b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line.decode(ENCODING))
                    except ValueError:
                        raise Disconnected("peer sent malformed JSON")
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout:
                raise
            except OSError as exc:
                raise Disconnected(str(exc))
            if not chunk:
                raise Disconnected("peer closed the connection")
            self.buf += chunk


def _enemy_view(e):
    intent = None
    if e.alive and e.current_move:
        intent = {"name": e.current_move.name,
                  "damage": e.current_move.damage}
    return {"name": e.name, "hp": e.hp, "max_hp": e.max_hp,
            "block": e.block, "alive": e.alive, "intent": intent,
            "statuses": {k.name: v for k, v in e.statuses.items() if v}}


def _player_view(p, is_me, engine=None):
    """A player row. Teammates carry a compact hand -- co-op sees each other."""
    summary = {}
    if not is_me and engine is not None:
        vals = summarise_hand(engine, p, ENV.MAX_HAND)
        summary = {n: round(v, 3)
                   for n, v in zip(ALLY_FEATURE_NAMES, vals) if v}
    return {"summary": summary, "name": p.name, "hp": p.hp, "max_hp": p.max_hp,
            "block": p.block, "energy": p.energy, "max_energy": p.max_energy,
            "alive": p.alive, "is_me": is_me,
            "draw": len(p.draw_pile), "discard": len(p.discard_pile),
            "hand": [{"name": c.name, "cost": str(c.current_cost(p)),
                      "upgraded": c.upgraded}
                     for c in p.hand[:ENV.MAX_HAND]],
            "statuses": {k.name: v for k, v in p.statuses.items() if v}}


def _card_view(engine, player, card, playable):
    return {"name": card.name, "cost": str(card.current_cost(player)),
            "type": card.card_type.name, "target": card.target.name,
            "text": card.current_description(), "playable": playable,
            "upgraded": card.upgraded}


def describe_action(env, action_id):
    """A human label for an action id, built from the engine's own state."""
    engine = env.engine
    if action_id == ENV.END_TURN_ACTION:
        return "end turn"
    player = env._current_player()
    if player is None:
        return "action {}".format(action_id)


    if action_id >= ENV.FIRST_CARD_ALLY_ACTION:
        off = action_id - ENV.FIRST_CARD_ALLY_ACTION
        slot, t = divmod(off, ENV.MAX_ALLY_TARGETS)
        hand = player.hand[:ENV.MAX_HAND]
        if slot >= len(hand):
            return "action {}".format(action_id)
        mate = env._player_at(t)
        return "play {} on {}".format(hand[slot].name,
                                      mate.name if mate else "?")

    slot, t = divmod(action_id, ENV.MAX_ENEMIES)
    hand = player.hand[:ENV.MAX_HAND]
    if slot >= len(hand):
        return "action {}".format(action_id)
    card = hand[slot]
    if card.target == TargetMode.SINGLE_ENEMY:
        foe = env._enemy_at(t)
        return "play {} at {}".format(card.name, foe.name if foe else "?")
    return "play {}".format(card.name)


def view_for(game, seat, your_turn, with_obs=False):
    """The whole state one client is allowed to see."""
    engine = game.engine
    players = engine.players
    order = players[seat:] + players[:seat]
    me = players[seat] if seat < len(players) else None

    return {
        "type": "state",
        "game": game.name,
        "turn": engine.turn_number,
        "your_turn": your_turn,
        "seat": seat,
        "players": [_player_view(p, p is me, engine) for p in order],
        "enemies": [_enemy_view(e) for e in engine.enemies],
        "hand": ([_card_view(engine, me, c,
                             c in engine.playable_cards(me))
                  for c in game.hand_of(seat)] if me else []),
        "moves": game.moves(seat) if (your_turn and me) else [],
        # Computed by the SERVER with the same _observe() training used, so an
        # agent cannot drift from what it learned by re-deriving it here.
        "obs": game.observation(seat) if with_obs else None,
        "over": engine.is_over,
    }


def listening_socket(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen(8)
    return s
