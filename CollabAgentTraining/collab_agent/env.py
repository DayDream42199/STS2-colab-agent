"""Gymnasium environment: one fight = one episode, the agent plays seat 0.

Actions (106):  0 end turn | 1-100 play hand slot h on target t | 101-103 choose k | 104 stop | 105 wait
Reward: Final_reward_norm (final_reward.py, default; the score paid as its change each step)
or the weighted team reward (config.RewardWeights).
"""
from collections import defaultdict

import numpy as np
import gymnasium as gym
from gymnasium import spaces

from .config import (EnvConfig, OBS_SIZE, N_ACTIONS, N_CHOICE, HAND_SIZE, N_TARGETS, N_PLAYERS,
                     OFF_PLAYERS, PLAYER_SIZE, OFF_CARDS, CARD_SIZE, OFF_PILES, N_PILES, PILE_SIZE,
                     OFF_EFFECTS, EFFECT_SIZE, obs_size, A_END, A_PLAY0, A_CHOOSE0, A_STOP, A_WAIT)
from . import engine as mock_engine
from .engine import new_stats
from .bots import make_bot, CheeseBot
from .analyzer import TeamProfiles, turn_evidence
from .observation import encode
from . import final_reward as FR
from . import styles

COMPONENTS = ("own_damage", "teammate_damage", "kill", "useful_block", "hp_lost", "knockout", "round", "result")


class DivideAndConquer:
    """Answers a question with more options than the 3 choice slots, in rounds of groups of up to 3."""

    def __init__(self, question):
        self.q = question
        self.pool = list(question.options)
        self.picks = []
        self.done = False
        self.single = False          # asking about one remaining option (choose it or stop)
        self._start_pick()

    def _start_pick(self):
        if len(self.picks) >= self.q.max_picks or not self.pool:
            self.done = True
            return
        if len(self.pool) == 1:
            if len(self.picks) < self.q.min_picks:     # forced: no need to ask
                self._pick(self.pool[0])
            else:
                self.single = True
                self.groups, self.idx = [[self.pool[0]]], 0
            return
        self.single = False
        self._start_round(list(self.pool))

    def _start_round(self, entrants):
        self.groups = [entrants[i:i + N_CHOICE] for i in range(0, len(entrants), N_CHOICE)]
        self.idx, self.winners = 0, []
        self._advance()

    def _advance(self):
        # a group of 1 passes through without asking
        while self.idx < len(self.groups) and len(self.groups[self.idx]) == 1:
            self.winners.append(self.groups[self.idx][0])
            self.idx += 1
        if self.idx == len(self.groups):
            if len(self.winners) == 1:
                self._pick(self.winners[0])
            else:
                self._start_round(self.winners)

    def _pick(self, card):
        self.picks.append(card)
        self.pool.remove(card)
        self._start_pick()

    @property
    def group(self):
        return [] if self.done else self.groups[self.idx]

    def can_stop(self):
        return len(self.picks) >= self.q.min_picks

    def choose(self, k):
        card = self.group[k]
        if self.single:
            self._pick(card)
            return
        self.winners.append(card)
        self.idx += 1
        self._advance()

    def stop(self):
        self.done = True             # keeps finished picks; mid-round winners are dropped


class CollabEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, config: EnvConfig = None, seed=None, fixed_team=None, strict=True):
        super().__init__()
        self.strict = strict                  # False: an illegal action is replaced by the first legal one
        self.cfg = config or EnvConfig()
        if self.cfg.reward_mode == "final":
            self.cfg.final.penalty.check()
        if self.cfg.swap_profiles and not self.cfg.style_profiles:
            raise ValueError("swap_profiles needs style_profiles (styles.load_or_make)")
        if self.cfg.engine == "real":
            from . import real_engine        # only when asked for: it needs 2nd_model next to this folder
            self.engine = real_engine
        elif self.cfg.engine == "mock":
            self.engine = mock_engine
        else:
            raise ValueError(f"engine must be 'mock' or 'real', not {self.cfg.engine!r}")
        if self.cfg.card_effects and self.cfg.engine != "real":
            raise ValueError("card_effects reads the real engine's cards: it needs engine 'real'")
        if getattr(self.cfg, "enemy_statuses", False) and self.cfg.engine != "real":
            raise ValueError("enemy_statuses reads the real engine's enemies: it needs engine 'real'")
        self.fixed_team = fixed_team          # e.g. ["aggressive", "defensive"] for evaluation
        self.observation_space = spaces.Box(-1.0, 1.0, shape=(obs_size(self.cfg),), dtype=np.float32)
        self.action_space = spaces.Discrete(N_ACTIONS)
        self.rng = np.random.default_rng(seed)
        self.ctime = 0                        # current training timestep (set by the trainer)
        self.players = None
        self.fights_left = 0
        self.swap_to = {}                     # seat -> the A, S, T the agent is shown instead (swap test)
        self.slots = list(range(N_PLAYERS))   # slot -> seat: whose numbers and targets each slot means (sort_teammates)
        self.team_profiles = TeamProfiles(self.cfg.profile_dir)

    # ------------------------------------------------------------ team / episode
    def _new_team(self):
        if self.fixed_team is not None:
            kinds = list(self.fixed_team)
        else:
            n = int(self.rng.integers(self.cfg.min_teammates, self.cfg.max_teammates + 1))
            kinds = [str(k) for k in self.rng.choice(self.cfg.teammate_types, size=n)]
        self.team_kinds = kinds
        bots = [make_bot(k, self.rng) for k in kinds]
        self.players = self.engine.make_team(self.rng, bots, self.cfg)
        self.team_profiles.new_team(range(1, len(self.players)))   # fresh profile per teammate
        self.fights_left = self.cfg.team_fights
        refs = self.cfg.style_profiles
        self.swap_to = ({seat: refs[styles.farthest(kind, refs)] if kind in refs else None     # None: see _shown
                         for seat, kind in enumerate(kinds, start=1)} if self.cfg.swap_profiles else {})

    def reset(self, seed=None, options=None):
        if seed is not None:
            super().reset(seed=seed)
            self.rng = self.np_random
            self.players = None               # a seeded reset starts a fresh team
        if self.players is None or self.fights_left <= 0:
            self._new_team()
            self._play_history()
        self.fights_left -= 1
        return self._start_fight(), {}

    def _play_history(self):
        """A team with history: it plays cfg.history_fights fights before the agent meets it, the
        Cheese bot in the agent's seat, so the profiles the agent first sees are built from play."""
        stand_in = CheeseBot()
        for _ in range(self.cfg.history_fights):
            self._start_fight()
            done = False
            while not done:
                _, _, done, _, _ = self.step(styles.cheese_action(self, stand_in))

    def _start_fight(self):
        for _ in range(20):
            self.combat = self.engine.new_fight(self.rng, self.players, self.cfg)
            self.dc = None
            self.waited = False
            self._teammate_lead()
            if self.combat.result is None:
                break
        self._ask(self.combat.pending_question(0))      # a question at the very start of the fight
        self.ep = defaultdict(float)
        self.ep_return = 0.0
        # the first read of the score; each step is then paid the change since the last read
        self.start_score = self.prev_score = FR.score(self._fight_summary(), self.cfg.final.penalty)
        return self._obs()

    def _teammate_lead(self):
        """At turn start, teammates may act before the agent looks (simultaneous turns)."""
        if self.cfg.no_wait or self.cfg.blind_teammates:
            return
        for p in self.combat.players[1:]:
            if p is not None and p.alive and self.rng.random() < self.cfg.teammate_lead_prob:
                for _ in range(int(self.rng.integers(1, 3))):
                    self.combat.bot_step(p.seat)

    # ------------------------------------------------------------ mask
    def action_masks(self):
        m = np.zeros(N_ACTIONS, dtype=bool)
        c = self.combat
        agent = c.players[0]
        if c.result is not None or not agent.alive:
            m[A_END] = True
            return m
        if self.dc is not None:
            for k in range(len(self.dc.group)):
                m[A_CHOOSE0 + k] = True
            if self.dc.can_stop():
                m[A_STOP] = True
            return m
        m[A_END] = True
        for h, t in c.legal_plays(0):
            m[A_PLAY0 + N_TARGETS * h + self.target_slot(t)] = True
        teammates_acting = any(p is not None and p.alive and not p.ended for p in c.players[1:])
        if teammates_acting and not self.waited and not (self.cfg.no_wait or self.cfg.blind_teammates):
            m[A_WAIT] = True
        return m

    def _obs(self):
        choice = self.dc.group if self.dc is not None else ()
        profiles = self.team_profiles.values
        if self.swap_to:                      # the agent sees another style's A, S, T; all else true
            profiles = {seat: self._shown(seat, p) if seat in self.swap_to else p for seat, p in profiles.items()}
        out = encode(self.combat, profiles, choice, self.waited, self.cfg.zero_profiles, self.cfg.blind_teammates,
                     self.cfg.card_effects, getattr(self.cfg, "enemy_statuses", False))
        if self.cfg.sort_teammates:
            self._sort_slots()
            out = self._in_slot_order(out)
        return out

    def _sort_slots(self):
        """Slot 1 up: the teammates most at risk first, knocked-out ones last, then the empty seats."""
        c = self.combat
        here = [s for s in range(1, len(c.players)) if c.players[s] is not None]
        here.sort(key=lambda s: (not c.players[s].alive, c.players[s].hp - max(0, c.incoming(s) - c.players[s].block), s))
        self.slots = [0] + here + [s for s in range(1, N_PLAYERS) if s not in here]

    def _in_slot_order(self, raw):
        """Each teammate's numbers, hand and piles (and its hand's card effects) moved to their slot. Nothing else in the
        input depends on a seat (the enemy-status block is by enemy)."""
        out = raw.copy()
        blocks = ((OFF_PLAYERS, PLAYER_SIZE), (OFF_CARDS, HAND_SIZE * CARD_SIZE), (OFF_PILES, N_PILES * PILE_SIZE))
        if self.cfg.card_effects:
            blocks += ((OFF_EFFECTS, HAND_SIZE * EFFECT_SIZE),)
        for slot, seat in enumerate(self.slots):
            if slot != seat:
                for off, size in blocks:
                    out[off + slot * size:off + (slot + 1) * size] = raw[off + seat * size:off + (seat + 1) * size]
        return out

    def target_seat(self, t):
        """The real target of an action's target number: a teammate's slot becomes their seat."""
        return self.slots[t] if 1 <= t < N_PLAYERS else t

    def target_slot(self, t):
        """The action's target number for a real target: a teammate's seat becomes their slot."""
        return self.slots.index(t) if 1 <= t < N_PLAYERS else t

    def _shown(self, seat, p):
        """A teammate's profile with another style's A, S, T. A blend bot has no style to swap
        from: the named style furthest from its profile as it stands."""
        other = self.swap_to[seat] or self.cfg.style_profiles[styles.farthest_from(p, self.cfg.style_profiles)]
        return dict(p, **{k: other[k] for k in "AST"})

    # ------------------------------------------------------------ step
    def step(self, action):
        action = int(action)
        c = self.combat
        mask = self.action_masks()
        if not mask[action]:
            if self.strict:
                raise ValueError(f"illegal action {action}")
            action = int(np.flatnonzero(mask)[0])

        if self.dc is not None:                                 # answering a question
            if action == A_STOP:
                self.dc.stop()
            else:
                self.dc.choose(action - A_CHOOSE0)
            if self.dc.done:
                self._ask(c.answer_question(self.dc.picks))
        elif A_PLAY0 <= action < A_CHOOSE0:                     # play hand slot h on target t
            h, t = divmod(action - A_PLAY0, N_TARGETS)
            self._ask(c.play(0, h, self.target_seat(t)))
            self.waited = False
        elif action == A_WAIT:                                  # teammates take one action each
            before = c.version
            for p in c.players[1:]:
                if p is not None:
                    c.bot_step(p.seat)
            self.waited = c.version == before
        elif action == A_END:
            turn = c.turn
            c.end_turn(0)
            self._finish_teammates(turn)
            self.waited = False
        self._after_rounds()                  # an end, a wait or (real engine) an answer can finish a round

        # agent knocked out: the fight plays out without it (a question it held goes unanswered)
        if not c.players[0].alive:
            self.dc = None
        while c.result is None and not c.players[0].alive and c.turn <= self.cfg.max_rounds:
            turn = c.turn
            self._finish_teammates(turn)
            self._after_rounds(lead=False)
            if c.result is None and c.turn == turn:   # never spin: say what the round is waiting on
                raise RuntimeError(f"round {turn} cannot end with the agent knocked out: "
                                   f"{getattr(c, 'stall_report', lambda: '')()}")
        if self.dc is None and c.result is None and c.players[0].alive:
            self._ask(c.pending_question(0))  # one asked by a teammate's card, or at turn start

        if c.result is None and c.turn > self.cfg.max_rounds:
            c.result = "lose"

        terminated = c.result is not None
        reward, comps, extras = self._reward(terminated)
        c.stats = new_stats()
        for k, v in {**comps, **extras}.items():
            self.ep[k] += v
        self.ep_return += reward
        info = {"reward_components": comps}
        if terminated:
            fight = self._fight_summary()
            info["is_success"] = c.result == "win"
            # score_std: the default weights, so runs trained on different weights can be compared
            info["episode_summary"] = dict(self.ep, win=float(c.result == "win"), rounds=c.turn,
                                           ally_hp_frac=fight["ally_hp"] / fight["ally_max_hp"],
                                           self_alive=float(fight["self_alive"]),
                                           mates_alive=fight["mates_alive"] / max(1, fight["mates"]),
                                           score_std=FR.score(fight, FR.PenaltyWeights()),
                                           team="+".join(self.team_kinds), ret=self.ep_return)
        return self._obs(), reward, terminated, False, info

    def _ask(self, q):
        """Put question q to the agent through Divide and Conquer. One with nothing to ask is
        answered at once, and so is whatever comes after it, until a real question or none."""
        while q is not None:
            self.dc = DivideAndConquer(q)
            if not self.dc.done:
                return
            q = self.combat.answer_question(self.dc.picks)
        self.dc = None

    def _finish_teammates(self, turn):
        """Teammates still acting finish this turn (stops as soon as the round resolves)."""
        c = self.combat
        for p in c.players[1:]:
            if p is not None and c.result is None and c.turn == turn:
                c.bot_finish_turn(p.seat)

    def _after_rounds(self, lead=True):
        """If a round resolved: update teammate profiles, tell bots, let teammates lead the new turn."""
        c = self.combat
        if not c.finished_histories:
            return
        if 0 in c.finished_histories:        # f_0_variant3: the agent's turn against the profiles it played with
            seats = [p.seat for p in c.players[1:] if p is not None]
            c.stats["complement"] += FR.complement(turn_evidence(c.finished_histories[0]),
                                                   self.team_profiles.values, seats)
        for seat, hist in c.finished_histories.items():
            if seat > 0:
                self.team_profiles.update(seat, hist)              # CharacteristicAnalyzer package
                c.players[seat].bot.on_turn_end()
        c.finished_histories = {}
        if lead and c.result is None and c.players[0].alive:
            self._teammate_lead()

    def set_ctime(self, t):
        self.ctime = t

    def _fight_summary(self):
        c = self.combat
        team = [p for p in c.players if p is not None]
        me, mates = team[0], team[1:]
        # every enemy that has been in the fight counts toward the pool, those summoned later too
        return dict(win=c.result == "win", lost=c.result == "lose",
                    ally_hp=sum(p.hp for p in team), ally_max_hp=sum(p.max_hp for p in team),
                    allies_alive=sum(p.alive for p in team), allies=len(team),
                    self_hp=me.hp, self_max_hp=me.max_hp, self_alive=me.alive,
                    mate_hp=sum(p.hp for p in mates), mate_max_hp=sum(p.max_hp for p in mates),
                    mates_alive=sum(p.alive for p in mates), mates=len(mates),
                    enemy_hp=sum(e.hp for e in c.living_enemies()), enemy_max_hp=c.total_enemy_max_hp,
                    turns=c.turn)

    def _reward(self, terminated):
        """Returns (reward, parts that sum to the reward, extra numbers only for logging)."""
        if self.cfg.reward_mode == "weighted":
            r, comps = self._weighted_reward()
            extras = {}
            if terminated:                    # the score is how every agent is judged, whatever trained it
                penalty, pen_parts = FR.general_penalty(self._fight_summary(), self.cfg.final.penalty)
                extras.update(pen_parts, penalty=penalty, score=100 - penalty)
            return r, comps, extras
        fr, c = self.cfg.final, self.combat
        fight = self._fight_summary()
        ctx = dict(profiles=self.team_profiles.values, teammates=[p.seat for p in c.players[1:] if p is not None],
                   enemy_pool=fight["enemy_max_hp"], ally_pool=fight["ally_max_hp"])
        parts = {name: fn(c.stats, ctx) for name, fn in FR.SCORINGS.items()}
        f_train = FR.weighted(parts[fr.collab.scoring], fr.collab)
        decay = FR.decay_factor(self.ctime, fr.collab, fr.total_timesteps)
        penalty, pen_parts = FR.general_penalty(fight, fr.penalty)
        score = 100 - penalty
        comps = {"general": (score - self.prev_score) / 100, "collab": f_train / 50 * decay}
        self.prev_score = score
        # every scoring, each at its own starting weights so runs can be compared; f_train is
        # the one this agent learns from, at its own weights
        extras = {f"f_{name}": FR.weighted_by(p, FR.DEFAULT_WEIGHTS[name]) for name, p in parts.items()}
        extras["f_train"] = f_train
        # the same ruler for every agent, whatever trains it: bonus enemy HP from its Vulnerable, %
        extras["assist_share"] = parts["variant1"]["offense"]
        if terminated:
            extras.update(pen_parts, penalty=penalty, score=score)
        return float(sum(comps.values())), comps, extras

    def _weighted_reward(self):
        c, w, st = self.combat, self.cfg.reward, self.combat.stats
        n_players = sum(p is not None for p in c.players)
        total_hp = c.total_enemy_max_hp
        comps = {
            "own_damage": w.own_damage * st["damage"][0] / total_hp,
            "teammate_damage": w.teammate_damage * sum(st["damage"][1:]) / total_hp,
            "kill": w.kill * st["kills"][0],
            "useful_block": w.useful_block * st["useful_block"][0],
            "hp_lost": -w.hp_lost * sum(st["hp_lost_frac"]) / n_players,
            "knockout": -w.knockout * st["knockouts"],
            "round": -w.round * st["rounds"],
            "result": w.win if c.result == "win" else -w.lose if c.result == "lose" else 0.0,
        }
        return float(sum(comps.values())), comps
