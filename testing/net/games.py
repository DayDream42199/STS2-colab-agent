# -*- coding: utf-8 -*-
"""The two games the server can host, behind one interface."""

import game_engine.env as ENV
from game_engine.cards import TargetMode
from testing import config


class acting_as(object):
    """Point a game's 'current player' at `seat` for the duration of a block."""

    def __init__(self, obj, attr, seat):
        self.obj, self.attr, self.seat = obj, attr, seat

    def __enter__(self):
        self.prev = getattr(self.obj, self.attr)
        setattr(self.obj, self.attr, self.seat)
        return self.obj

    def __exit__(self, *exc):
        setattr(self.obj, self.attr, self.prev)
        return False


class FullGame(object):
    """The whole game: 221 action ids, the real card pool, config.json."""

    name = "full"

    def __init__(self, cfg, n_players, seed=None):
        self.cfg, self.n_players, self.seed = cfg, n_players, seed
        self.env = None

    def reset(self):
        self.env = ENV.CombatEnv(self._players, self._enemies, seed=self.seed)
        self.env.reset()

    def _players(self):
        party = config.build_party(self.cfg)
        while len(party) < self.n_players:
            extra = config.build_party(self.cfg)[-1]
            extra.name = "Hero {}".format(len(party) + 1)
            party.append(extra)
        return party[:self.n_players]

    def _enemies(self):
        import testing.play as play
        key = str(self.cfg.get("encounter") or "1")
        spec = play.ENCOUNTERS.get(key) or play.ENCOUNTERS["1"]
        foes = spec[1]
        return foes() if callable(foes) else list(foes)

    @property
    def engine(self):
        return self.env.engine

    @property
    def action_space(self):
        return self.env.action_space_size()

    @property
    def end_turn_id(self):
        return ENV.END_TURN_ACTION

    def _seat(self, seat):
        return acting_as(self.env, "active_player_idx", seat)

    def hand_of(self, seat):
        p = self.engine.players[seat]
        return [c for c in p.hand[:ENV.MAX_HAND]]

    def legal_mask(self, seat):
        with self._seat(seat) as env:
            return env.legal_action_mask()

    def label_for(self, seat, action_id):
        from testing.net import protocol as P
        with self._seat(seat) as env:
            return P.describe_action(env, action_id)

    def moves(self, seat):
        """One move per card, carrying the targets it may be aimed at."""
        with self._seat(seat) as env:
            player = env._current_player()
            if player is None:
                return []
            grouped, order = {}, []
            for action_id, ok in enumerate(env.legal_action_mask()):
                if not ok:
                    continue
                key, t = _full_key(action_id)
                if key not in grouped:
                    grouped[key] = []
                    order.append(key)
                grouped[key].append((action_id, t))

            moves = []
            for kind, slot in order:
                ids = grouped[(kind, slot)]
                if kind == "end":
                    moves.append(_move("end turn", "",
                                       [{"id": ids[0][0], "label": ""}]))
                    continue
                hand = player.hand[:ENV.MAX_HAND]
                if slot >= len(hand):
                    continue
                card = hand[slot]
                label = "[{}] {}".format(card.current_cost(player), card.name)
                text = card.current_description()
                targets = []
                for action_id, t in ids:
                    who = (env._player_at(t) if kind == "ally"
                           else env._enemy_at(t))
                    targets.append({"id": action_id,
                                    "label": _target_label(who)})
                if len(targets) == 1:
                    targets[0]["label"] = ""
                moves.append(_move(label, text, targets))
            return moves

    def observation(self, seat):
        """The exact vector training used, built as `seat`."""
        with self._seat(seat) as env:
            return [float(x) for x in env._observe()]

    def apply(self, seat, action_id):
        with self._seat(seat):
            self.env.step(action_id)

    def end_round(self):
        engine = self.engine
        engine.end_player_turn()
        if not engine.is_over:
            engine.run_enemy_turn()
        if not engine.is_over:
            engine.start_player_turn()


class SimpleGame(object):
    """The cut-down game: Strike, Defend, end turn."""

    name = "simple"

    def __init__(self, cfg, n_players, seed=None):
        from testing.simple import SimpleEnv
        kw = config.simple_kwargs(cfg)
        kw["players"] = n_players
        self.kw, self.seed = kw, seed
        self.env = SimpleEnv(**kw)

    def reset(self):
        self.env.reset(seed=self.seed)

    @property
    def engine(self):
        return self.env.engine

    @property
    def action_space(self):
        return 3

    @property
    def end_turn_id(self):
        from testing.simple import END_TURN
        return END_TURN

    def _seat(self, seat):
        return acting_as(self.env, "active_idx", seat)

    def hand_of(self, seat):
        return list(self.engine.players[seat].hand)

    def legal_mask(self, seat):
        with self._seat(seat) as env:
            return env.legal_actions()

    def label_for(self, seat, action_id):
        from testing.simple import ACTION_NAMES
        if 0 <= action_id < len(ACTION_NAMES):
            return ACTION_NAMES[action_id]
        return "action {}".format(action_id)

    def moves(self, seat):
        from testing.simple import PLAY_STRIKE, PLAY_DEFEND, END_TURN
        with self._seat(seat) as env:
            me = env.player
            if me is None or not me.alive:
                return []
            legal = env.legal_actions()
            foe = env.enemy
            moves = []
            for action_id, wanted in ((PLAY_STRIKE, "Strike"),
                                      (PLAY_DEFEND, "Defend")):
                if not legal[action_id]:
                    continue
                card = next((c for c in me.hand if c.name == wanted), None)
                label = "[{}] {}".format(card.current_cost(me) if card else 1,
                                         wanted)
                text = card.current_description() if card else ""
                moves.append(_move(label, text,
                                   [{"id": action_id, "label": ""}]))
            if legal[END_TURN]:
                moves.append(_move("end turn", "",
                                   [{"id": END_TURN, "label": ""}]))
            return moves

    def observation(self, seat):
        """The exact vector training used, built as `seat`."""
        with self._seat(seat) as env:
            return [float(x) for x in env._observe()]

    def apply(self, seat, action_id):
        with self._seat(seat):
            self.env.step(action_id)

    def end_round(self):
        engine = self.engine
        engine.end_player_turn()
        if not engine.is_over:
            engine.run_enemy_turn()
        if not engine.is_over:
            engine.start_player_turn()


def _move(label, text, targets):
    return {"label": label, "text": text, "targets": targets}


def _target_label(who):
    if who is None:
        return "?"
    if hasattr(who, "max_hp"):
        return "{} ({}/{} hp)".format(who.name, who.hp, who.max_hp)
    return who.name


def _full_key(action_id):
    """Which (kind, slot) a full-game action belongs to, and its target."""
    if action_id == ENV.END_TURN_ACTION:
        return ("end", 0), None
    if action_id >= ENV.FIRST_CARD_ALLY_ACTION:
        off = action_id - ENV.FIRST_CARD_ALLY_ACTION
        slot, t = divmod(off, ENV.MAX_ALLY_TARGETS)
        return ("ally", slot), t
    slot, t = divmod(action_id, ENV.MAX_ENEMIES)
    return ("card", slot), t


def build(kind, cfg, n_players, seed=None):
    return (SimpleGame if kind == "simple" else FullGame)(cfg, n_players, seed)
