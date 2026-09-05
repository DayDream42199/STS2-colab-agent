# -*- coding: utf-8 -*-
"""An agent as a network client. Connects like a human, plays from a policy.

    python testing/net/agent.py --random
    python testing/net/agent.py --model testing/simple_agent.pt
    python testing/net/agent.py --model runs/ppo.zip --name Bot

It asks the server for `obs` -- the same vector _observe() produced during
training -- rather than rebuilding one from the JSON. One implementation of
the features, so the agent cannot drift from what it learned.
"""

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(
    _os.path.dirname(_os.path.abspath(__file__)))))


import queue
import random
import socket
import threading

from testing.net import protocol as P


class RandomPolicy(object):
    name = "random"

    def __init__(self, seed=None):
        self.rng = random.Random(seed)

    def choose(self, obs, legal_ids, n_actions):
        return self.rng.choice(legal_ids)


class TorchPolicy(object):
    """A train_torch.py checkpoint (.pt)."""

    def __init__(self, path):
        import torch
        from testing.train_torch import load
        self.torch = torch
        self.policy, self.updates = load(path)
        self.n_obs = self.policy.n_obs
        self.name = "{} ({} updates)".format(_os.path.basename(path),
                                             self.updates)

    def choose(self, obs, legal_ids, n_actions):
        torch = self.torch
        if len(obs) != self.n_obs:
            raise ValueError(
                "this agent expects {} observation floats, the server sent {} "
                "-- it was trained against a different game or party size"
                .format(self.n_obs, len(obs)))
        mask = torch.zeros(n_actions, dtype=torch.bool)
        for i in legal_ids:
            if i < n_actions:
                mask[i] = True
        with torch.no_grad():
            logits = self.policy(torch.as_tensor(obs, dtype=torch.float32), mask)
        return int(torch.argmax(logits))


class SB3Policy(object):
    """A MaskablePPO checkpoint (.zip)."""

    def __init__(self, path):
        import numpy as np
        from sb3_contrib import MaskablePPO
        self.np = np
        self.model = MaskablePPO.load(path)
        self.name = _os.path.basename(path)

    def choose(self, obs, legal_ids, n_actions):
        np = self.np
        mask = np.zeros(n_actions, dtype=bool)
        for i in legal_ids:
            if i < n_actions:
                mask[i] = True
        action, _ = self.model.predict(np.asarray(obs, dtype=np.float32),
                                       action_masks=mask, deterministic=True)
        return int(action)


def build_policy(argv):
    path = _arg(argv, "--model")
    if path is None:
        return RandomPolicy(_arg(argv, "--seed", None, int))
    if path.endswith(".zip"):
        return SB3Policy(path)
    return TorchPolicy(path)


def _is_end_turn(state, action_id):
    return any(m["label"] == "end turn" and t["id"] == action_id
               for m in state["moves"] for t in m["targets"])


def legal_ids_from(state):
    """Every action id the server says is legal, flattened out of `moves`."""
    return [t["id"] for m in state["moves"] for t in m["targets"]]


def run(host, port, name, policy, verbose=True):
    sock = socket.create_connection((host, port))
    P.send(sock, {"type": "join", "name": name, "wants_obs": True})
    inbox = queue.Queue()

    def reader():
        try:
            for msg in P.LineReader(sock).messages():
                inbox.put(msg)
        except P.Disconnected:
            pass
        inbox.put(None)

    threading.Thread(target=reader, daemon=True).start()
    print("{} connected to {}:{} using {}".format(name, host, port, policy.name))

    n_actions, acted, ended_on_turn = None, 0, None
    while True:
        batch = [inbox.get()]
        # Drain whatever else has arrived. Acting on the FIRST queued state
        # rather than the newest is a stale read: by the time the agent
        # replies, that board is several actions old, and the server
        # correctly refuses the move. A human client hides this because a
        # person is slow enough that the queue is usually empty; an agent
        # replies in microseconds and outruns its own inbox.
        while True:
            try:
                batch.append(inbox.get_nowait())
            except queue.Empty:
                break

        msg = None
        for item in batch:
            if item is None:
                print("  server closed the connection")
                return acted
            kind = item.get("type")
            if kind == "welcome":
                n_actions = item["action_space"]
                print("  seat {} of {}, {} actions".format(
                    item["seat"], item["of"], n_actions))
            elif kind == "error":
                print("  ! {}".format(item["text"]))
            elif kind == "over":
                print("  {} after {} turns".format(
                    "VICTORY" if item["victory"] else "DEFEAT", item["turns"]))
                return acted
            elif kind == "state":
                msg = item          # keep only the newest
        if msg is not None:
            if msg["over"] or not msg["your_turn"]:
                continue
            if msg.get("obs") is None:
                print("  ! the server sent no obs -- it did not honour "
                      "wants_obs, so this agent cannot play")
                P.send(sock, {"type": "quit"})
                return acted
            # We ended this round already. The server would refuse anything
            # else, and a stale state can still say your_turn -- so remember
            # it locally rather than learning it from a rejection.
            if ended_on_turn == msg["turn"]:
                continue
            legal = legal_ids_from(msg)
            if not legal:
                continue
            action = policy.choose(msg["obs"], legal, n_actions)
            if action not in legal:
                # A policy is allowed to be wrong; the server would refuse it
                # anyway, and arguing over a rejected move stalls the fight.
                action = legal[0]
            if verbose:
                label = next((t["label"] or m["label"]
                              for m in msg["moves"] for t in m["targets"]
                              if t["id"] == action), "?")
                print("  turn {}: {}".format(msg["turn"], label))
            if _is_end_turn(msg, action):
                ended_on_turn = msg["turn"]
            P.send(sock, {"type": "action", "id": action})
            acted += 1


def _arg(argv, flag, default=None, cast=str):
    if flag in argv:
        return cast(argv[argv.index(flag) + 1])
    return default


def main():
    argv = _sys.argv[1:]
    try:
        run(host=_arg(argv, "--host", "127.0.0.1"),
            port=_arg(argv, "--port", P.PORT, int),
            name=_arg(argv, "--name", "Agent"),
            policy=build_policy(argv))
    except ConnectionRefusedError:
        print("no server there -- start it with "
              "`python testing/net/server.py` first")
    except KeyboardInterrupt:
        print("\n  (quit)")


if __name__ == "__main__":
    main()
