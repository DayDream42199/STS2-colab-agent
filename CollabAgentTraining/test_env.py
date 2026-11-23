"""Quick checks before training:  python test_env.py"""
import numpy as np
from gymnasium.utils.env_checker import check_env

from collab_agent.config import EnvConfig, OBS_SIZE, A_CHOOSE0, A_STOP
from collab_agent.env import CollabEnv, DivideAndConquer
from collab_agent.engine import Question
from collab_agent.cards import Card


def test_random_rollouts(episodes=200):
    env = CollabEnv(EnvConfig(), seed=0)
    rng = np.random.default_rng(0)
    obs, _ = env.reset()
    done_eps = 0
    while done_eps < episodes:
        assert obs.shape == (OBS_SIZE,) and obs.dtype == np.float32
        assert -1.0 <= obs.min() and obs.max() <= 1.0, "observation out of range"
        m = env.action_masks()
        assert m.any(), "mask has no legal action"
        if env.dc is not None:
            assert not m[:A_CHOOSE0].any() and not m[105], "only choose/stop inside a question"
        obs, r, term, trunc, info = env.step(int(rng.choice(np.flatnonzero(m))))
        assert np.isfinite(r)
        if term:
            done_eps += 1
            obs, _ = env.reset()
    print(f"ok  {episodes} random fights, masks always legal, inputs in [-1, 1]")


def test_divide_and_conquer():
    opts = [Card("Strike") for _ in range(8)]
    q = Question(0, Card("Purge"), opts, min_picks=0, max_picks=2, draw_per_pick=1)
    dc = DivideAndConquer(q)
    asks = 0
    while not dc.done:
        assert 1 <= len(dc.group) <= 3
        dc.choose(len(dc.group) - 1)
        asks += 1
    assert len(dc.picks) == 2 and len(set(c.uid for c in dc.picks)) == 2
    dc2 = DivideAndConquer(Question(0, Card("Purge"), opts, 0, 2, 1))
    dc2.stop()
    assert dc2.done and dc2.picks == []
    print(f"ok  Divide and Conquer: 8 options, 2 picks in {asks} questions; stop keeps 0 picks")


def test_gym_api():
    check_env(CollabEnv(EnvConfig(), seed=1, strict=False), skip_render_check=True)
    print("ok  gymnasium API check")


def test_characteristic_analyzer():
    """Teammate profiles come from the CharacteristicAnalyzer package and separate the playstyles.
    Kept in memory, they are exactly what the package's own updateProfile gives for the same turns;
    with a profile_dir they are saved as its files too."""
    import json
    import os
    import tempfile
    import CharacteristicAnalyzer as CA
    from collab_agent.analyzer import TeamProfiles, to_history
    turns, real_update, real_new_team = [], TeamProfiles.update, TeamProfiles.new_team

    def recording(self, seat, turn):
        if seat == 1:
            turns.append(turn)
        real_update(self, seat, turn)

    def new_team(self, seats):                 # a new team starts its profiles from zero
        turns.clear()
        real_new_team(self, seats)
    TeamProfiles.update, TeamProfiles.new_team = recording, new_team
    results = {}
    try:
        for kind in ("aggressive", "defensive"):
            folder = tempfile.mkdtemp()
            env = CollabEnv(EnvConfig(team_fights=20, profile_dir=folder), seed=3, fixed_team=[kind, kind])
            rng = np.random.default_rng(3)
            env.reset()
            for _ in range(3000):
                m = env.action_masks()
                _, _, term, _, _ = env.step(int(rng.choice(np.flatnonzero(m))))
                if term:
                    env.reset()
            results[kind] = env.team_profiles.get(1)
            saved = os.path.join(folder, f"{env.team_profiles.tag}_seat1.json")
            assert json.load(open(saved))["A"] == results[kind]["A"]
            CA.setProfileDir(tempfile.mkdtemp())           # the same turns through the package's API
            CA.newProfile("check", "check", overwrite=True)
            for turn in turns:
                theirs = CA.updateProfile("check", to_history(turn))
            assert turns and theirs == results[kind], (theirs, results[kind])
    finally:
        TeamProfiles.update, TeamProfiles.new_team = real_update, real_new_team
    assert results["aggressive"]["A"] > 0.3 and results["defensive"]["A"] < -0.3, results
    print(f"ok  CharacteristicAnalyzer package: aggressive A={results['aggressive']['A']:+.2f}, "
          f"defensive A={results['defensive']['A']:+.2f}; in memory = the package's own updateProfile")


def test_final_reward():
    from collab_agent import final_reward as FR
    w = FR.PenaltyWeights()
    assert abs(FR.turn_cost(0, 6, 10, 0.35)) < 1e-12                       # 0 at turn 0
    assert 0.45 < FR.turn_cost(8, 6, 10, 0.35) < 0.55                       # about half way at m
    assert FR.turn_cost(40, 6, 10, 0.35) > 0.999                            # -> 1
    try:
        FR.turn_cost(5, 6, 6, 0.35)
        raise AssertionError("s = 0 must raise")
    except ValueError:
        pass
    win = dict(lost=False, ally_hp=200, ally_max_hp=200, allies_alive=3, allies=3, enemy_hp=0, enemy_max_hp=300, turns=0)
    assert FR.general_penalty(win, w)[0] == 0                               # perfect fight: no penalty
    lose = dict(lost=True, ally_hp=0, ally_max_hp=200, allies_alive=0, allies=3, enemy_hp=300, enemy_max_hp=300, turns=1000)
    assert abs(FR.general_penalty(lose, w)[0] - (100 + w.E)) < 1e-6         # worst fight: A+B+C+D = 100, E on top
    going = dict(lose, lost=False, ally_hp=100, allies_alive=3)
    assert FR.general_penalty(going, w)[1]["pen_A"] == 0                    # mid-fight: A only once lost
    worst_win = dict(lost=False, ally_hp=1, ally_max_hp=320, allies_alive=1, allies=4, enemy_hp=0, enemy_max_hp=300,
                     turns=1000)
    best_loss = dict(lost=True, ally_hp=0, ally_max_hp=320, allies_alive=0, allies=4, enemy_hp=1, enemy_max_hp=300,
                     turns=1)
    assert FR.score(worst_win, w) > FR.score(best_loss, w)                  # any win beats any loss
    odd = dict(going, enemy_hp=999_999_999, ally_hp=-50)                    # engine numbers past the pools
    assert FR.general_penalty(odd, w)[1]["pen_D"] == w.D and FR.general_penalty(odd, w)[1]["pen_B"] == w.B
    for bad in (FR.PenaltyWeights(45, 10, 25, 15, 5), FR.PenaltyWeights(25, 10, 25, 40, 40),
                FR.PenaltyWeights(35, 5, 5, 15, 5, B_team=15, C_team=26),          # teammates apart: not 100
                FR.PenaltyWeights(35, 20, 30, 15, 5, B_team=0),                    # only one of the pair
                FR.PenaltyWeights(35, 5, 5, 15, 40, B_team=15, C_team=25)):        # E too big: 40 is not under 35 + 5
        try:
            bad.check()
            raise AssertionError(f"{bad} must be refused")
        except ValueError:
            pass
    # teammates apart: a teammate's knockout and the agent's own cost what their weights say
    split = FR.PenaltyWeights(35, 5, 5, 15, 5, B_team=15, C_team=25).check()
    full = dict(lost=False, ally_hp=240, ally_max_hp=240, allies_alive=3, allies=3, enemy_hp=0, enemy_max_hp=300, turns=0,
                self_hp=80, self_max_hp=80, self_alive=True, mate_hp=160, mate_max_hp=160, mates_alive=2, mates=2)
    mate_down = dict(full, ally_hp=160, allies_alive=2, mate_hp=80, mates_alive=1)
    self_down = dict(full, ally_hp=160, allies_alive=2, self_hp=0, self_alive=False)
    assert FR.general_penalty(full, split)[0] == 0
    assert abs(FR.general_penalty(mate_down, split)[0] - 20) < 1e-9 and abs(FR.general_penalty(self_down, split)[0] - 10) < 1e-9
    assert abs(FR.general_penalty(mate_down, w)[0] - 40 / 3) < 1e-9 and abs(FR.general_penalty(self_down, w)[0] - 40 / 3) < 1e-9
    wiped = dict(full, lost=True, ally_hp=0, allies_alive=0, self_hp=0, self_alive=False, mate_hp=0, mates_alive=0, enemy_hp=300, turns=1000)
    assert abs(FR.general_penalty(wiped, split)[0] - (100 + split.E)) < 1e-6
    for last_one in (dict(self_hp=1, self_alive=True, mate_hp=0, mates_alive=0), dict(self_hp=0, self_alive=False, mate_hp=1, mates_alive=1)):
        slow_win = dict(full, ally_hp=1, allies_alive=1, turns=1000, **last_one)
        quick_loss = dict(wiped, enemy_hp=1, turns=1)
        assert FR.score(slow_win, split) > FR.score(quick_loss, split)      # any win still beats any loss
    c = FR.CollabSettings(cdecay=0.5)
    assert FR.decay_factor(0, c, 1000) == 1.0 and FR.decay_factor(500, c, 1000) == 0.5
    assert FR.decay_factor(2000, c, 1000) == 0.5                             # min(CTime/DTime, 1)
    print("ok  Final_reward_norm: turn cost, A + B + C + D = 100 with E on top, win beats loss, decay")


def test_reward_per_step(episodes=60):
    """Paid as the change each step: over a fight the general part adds up to (final - start) / 100."""
    env = CollabEnv(EnvConfig(), seed=5)
    rng = np.random.default_rng(5)
    env.reset()
    total, done_eps, seen = 0.0, 0, set()
    while done_eps < episodes:
        _, r, term, _, info = env.step(int(rng.choice(np.flatnonzero(env.action_masks()))))
        comps = info["reward_components"]
        assert abs(r - comps["general"] - comps["collab"]) < 1e-9
        total += comps["general"]
        for p in env.combat.players:
            assert p is None or p.alive or p.history is None, "a knocked-out player's last turn is not handed over again"
        if term:
            s = info["episode_summary"]
            assert abs(total - (s["score"] - env.start_score) / 100) < 1e-9, (total, s["score"], env.start_score)
            seen.update(k for k in s if k.startswith("f_") and s[k] != 0)
            total, done_eps = 0.0, done_eps + 1
            env.reset()
    assert {"f_baseline", "f_variant1", "f_variant2", "f_variant3", "f_variant4", "f_train"} <= seen, seen
    print(f"ok  {episodes} fights: per-step general reward adds up to the final score; every scoring fires")


def test_analyzer_history():
    """The analyzer gets each used card as it showed in hand, and the Block at turn end."""
    from collab_agent.analyzer import to_history, turn_evidence
    turn = {"E_total": 1, "used": [[1, 6, 0, {"now"}]], "leftover": [[1, 0, 5, {"now", "self"}]],
            "intent": 10, "start_block": 0, "end_block": 8}
    h = to_history(turn)
    assert len(h) == 5 and h[4] == 8 and h[1] == [[1, 6, 0, ["now"]]]
    no_end = dict(turn)
    del no_end["end_block"]
    assert len(to_history(no_end)) == 4
    ev = turn_evidence(turn)
    assert set(ev) == {"e_A", "e_S", "e_T", "w_A", "w_S", "w_T"}
    # 8 Block from a teammate (none from the used cards) leaves I = 2: the held Defend was worth
    # 0.4 energy, so the Strike says less about Aggression than with all 10 coming (w 0.4 vs 1)
    uncovered = turn_evidence(dict(turn, end_block=0))
    assert abs(ev["w_A"] - 0.4) < 1e-9 and abs(uncovered["w_A"] - 1) < 1e-9, (ev, uncovered)
    print("ok  analyzer input: shown values, Block at turn end, evidence without a profile")


def test_swapped_profiles():
    """The swap changes only the agent's input; a policy that ignores it scores the same (Adv = 0)."""
    import dataclasses
    from collab_agent import styles
    from evaluate import run_with_advantage, policy_cheese
    refs = {"aggressive": {"A": 0.9, "S": 0.0, "T": 0.8}, "defensive": {"A": -0.7, "S": 0.0, "T": -0.6},
            "cheese": {"A": 0.3, "S": 0.0, "T": 0.2}, "random": {"A": 0.1, "S": 0.1, "T": 0.1},
            "change": {"A": 0.5, "S": 0.0, "T": 0.4}, "support": {"A": 0.2, "S": 0.3, "T": 0.9}}
    assert styles.farthest("aggressive", refs) == "defensive"
    cfg = EnvConfig()
    true_env = CollabEnv(cfg, seed=9, fixed_team=["aggressive"])
    swap_env = CollabEnv(dataclasses.replace(cfg, swap_profiles=True, style_profiles=refs), seed=9,
                         fixed_team=["aggressive"])
    true_env.reset(), swap_env.reset()
    true_env.team_profiles.values[1] = swap_env.team_profiles.values[1] = dict(A=0.8, S=0.0, T=0.7, c_A=0.3,
                                                                                c_S=0.0, c_T=0.3)
    assert not np.array_equal(true_env._obs(), swap_env._obs())
    r = run_with_advantage(cfg, ["aggressive", "defensive"], policy_cheese, 20, 3, refs)
    assert r["advantage"] == 0 and r["score"] == r["score_swapped"], r
    print("ok  swapped profiles: only the agent's input changes; the Cheese bot's advantage point is 0")


def test_teammates_option():
    """train.py --teammates: teams are drawn only from those bots; a name that is not a bot is refused."""
    from train import build_config
    env = CollabEnv(build_config(teammates=["aggressive"]), seed=11)
    seen = set()
    for _ in range(30):
        env.players = None                    # the next reset draws a new team
        env.reset()
        seen.update(env.team_kinds)
    assert seen == {"aggressive"}, seen
    assert build_config().teammate_types == EnvConfig().teammate_types      # by default: all six
    try:
        build_config(teammates=["agressive"])
        raise AssertionError("a misspelled bot must be refused")
    except ValueError:
        pass
    print("ok  --teammates: teams only from those bots, default all six, a wrong name refused")


def test_blend_bot():
    """Each blend bot rolls its own mix, always plays legally, and the swapped test can handle it."""
    import dataclasses
    from collab_agent import styles
    from collab_agent.bots import BlendBot, make_bot
    from evaluate import run_with_advantage, policy_cheese
    rng = np.random.default_rng(1)
    rolled = [make_bot("blend", rng) for _ in range(50)]
    assert all(isinstance(b, BlendBot) and abs(b.leanings.sum() - 1) < 1e-9 and 0 <= b.mistake <= 0.25 for b in rolled)
    assert len({round(b.leanings[0], 6) for b in rolled}) == 50                # no two the same
    assert not hasattr(rolled[0], "rng")                                       # answers as the scripted bots do
    env = CollabEnv(EnvConfig(), seed=2, fixed_team=["blend", "blend"])
    rng = np.random.default_rng(2)
    env.reset()
    fights = 0
    while fights < 40:
        _, _, done, _, _ = env.step(int(rng.choice(np.flatnonzero(env.action_masks()))))       # strict: raises if illegal
        if done:
            fights += 1
            env.reset()
    refs = {"aggressive": {"A": 0.9, "S": 0.0, "T": 0.8}, "defensive": {"A": -0.7, "S": 0.0, "T": -0.6},
            "cheese": {"A": 0.3, "S": 0.0, "T": 0.2}, "random": {"A": 0.1, "S": 0.1, "T": 0.1},
            "change": {"A": 0.5, "S": 0.0, "T": 0.4}, "support": {"A": 0.2, "S": 0.3, "T": 0.9}}
    assert styles.farthest_from({"A": 0.9, "S": 0.0, "T": 0.8}, refs) == "defensive"
    swap = CollabEnv(dataclasses.replace(EnvConfig(), swap_profiles=True, style_profiles=refs), seed=9, fixed_team=["blend"])
    true = CollabEnv(EnvConfig(), seed=9, fixed_team=["blend"])
    true.reset(), swap.reset()
    assert not np.array_equal(true._obs(), swap._obs())
    r = run_with_advantage(EnvConfig(), ["blend", "blend"], policy_cheese, 20, 3, refs)
    assert r["advantage"] == 0 and r["score"] == r["score_swapped"], r
    print("ok  blend bot: its own mix per bot, plays legally, swapped test changes only the input (Cheese bot's adv 0)")


def test_continuous_bot_and_history():
    """Continuous bot: x uniform per bot, x = 1 plays as aggressive, x = 0 as defensive.
    History: the agent's first fight with a new team already shows a built profile."""
    from collab_agent.bots import AggressiveBot, DefensiveBot, make_bot
    from evaluate import run_with_advantage, policy_cheese
    rng = np.random.default_rng(4)
    xs = [make_bot("continuous", rng).x for _ in range(2000)]
    assert 0 <= min(xs) and max(xs) <= 1 and abs(np.mean(xs) - 0.5) < 0.03 and abs(np.std(xs) - 0.2887) < 0.02
    env = CollabEnv(EnvConfig(), seed=4, fixed_team=["continuous"])
    env.reset()
    bot = env.players[1].bot
    for x, same in ((1.0, AggressiveBot()), (0.0, DefensiveBot())):
        bot.x = x
        assert bot.act(env.combat, 1) == same.act(env.combat, 1)

    fresh = CollabEnv(EnvConfig(), seed=5, fixed_team=["aggressive"])
    built = CollabEnv(EnvConfig(history_fights=10), seed=5, fixed_team=["aggressive"])
    fresh.reset(), built.reset()
    assert fresh.team_profiles.get(1)["A"] == 0 and built.team_profiles.get(1)["A"] > 0.3, built.team_profiles.get(1)
    assert built.fights_left == fresh.fights_left == EnvConfig().team_fights - 1      # history is not the team's fights
    assert built.ep_return == 0 and not built.ep and built.combat.result is None     # the agent's fight starts clean
    obs, r, *_ = built.step(int(np.flatnonzero(built.action_masks())[0]))
    assert obs.shape == (OBS_SIZE,) and np.isfinite(r)
    r = run_with_advantage(EnvConfig(history_fights=2), ["continuous", "continuous"], policy_cheese, 10, 3,
                           {k: {"A": a, "S": 0.0, "T": 0.0} for k, a in (("aggressive", 0.9), ("defensive", -0.7))})
    assert r["advantage"] == 0, r
    print("ok  continuous bot: x uniform, the ends play as aggressive and defensive; history builds the profile first")


def test_no_wait_and_blind(fights=20):
    """--no-wait: no Wait, teammates act only after the agent ends, their cards still shown.
    --blind-teammates: the same, their cards hidden. The profile is shown in both; without them the normal rules apply."""
    import dataclasses
    from collab_agent.config import OFF_CARDS, OFF_PILES, OFF_PLAYERS, PLAYER_SIZE, HAND_SIZE, CARD_SIZE, N_PLAYERS, N_PILES, PILE_SIZE, S, A_WAIT, A_END
    from train import build_config
    mates = (OFF_CARDS + HAND_SIZE * CARD_SIZE, OFF_CARDS + N_PLAYERS * HAND_SIZE * CARD_SIZE)
    piles = OFF_PILES + N_PILES * PILE_SIZE
    profile = OFF_PLAYERS + PLAYER_SIZE + 9 + S
    cfg = EnvConfig(teammate_lead_prob=1.0)

    seen = CollabEnv(cfg, seed=8, fixed_team=["aggressive", "defensive"])
    obs, _ = seen.reset()
    cls, calls = type(seen.combat), []
    original = cls.bot_step
    cls.bot_step = lambda self, seat: (calls.append(seat), original(self, seat))[1]
    try:
        seen.players = None
        obs, _ = seen.reset()
        assert calls and obs[mates[0]:mates[1]].any() and obs[piles:].any() and seen.action_masks()[A_WAIT]    # the normal rules

        for hidden, rule in ((False, dict(no_wait=True)), (True, dict(blind_teammates=True))):
            env = CollabEnv(dataclasses.replace(cfg, **rule), seed=8, fixed_team=["aggressive", "defensive"])
            rng = np.random.default_rng(8)
            profile_shown = False
            for _ in range(fights):
                calls.clear()
                obs, _ = env.reset()
                assert not calls, "a teammate acted before the agent's first look"
                assert obs[OFF_CARDS:mates[0]].any(), "the agent must still see its own hand"
                assert bool(obs[mates[0]:mates[1]].any()) != hidden and bool(obs[piles:].any()) != hidden
                done = False
                while not done:
                    mask = env.action_masks()
                    assert not mask[A_WAIT]
                    if hidden:
                        assert not obs[mates[0]:mates[1]].any() and not obs[piles:].any()
                    profile_shown = profile_shown or obs[profile:profile + 6].any()
                    action, turn = int(rng.choice(np.flatnonzero(mask))), env.combat.turn
                    calls.clear()
                    obs, _, done, _, _ = env.step(action)
                    if action != A_END and not done and env.combat.turn == turn and env.combat.players[0].alive:
                        assert not calls, "a teammate acted during the agent's turn"
            assert profile_shown, "the teammates' profile must still reach the agent"
    finally:
        cls.bot_step = original
    assert not build_config().no_wait and not build_config().blind_teammates
    assert build_config(no_wait=True).no_wait and build_config(blind_teammates=True).blind_teammates
    print("ok  --no-wait and --blind-teammates: no Wait, teammates act after the agent, cards shown or hidden, profile still shown; off by default")


def check_pair_symmetry(policy, obs):
    """--network pair: swapping two teammates, hand slots, enemies or choice slots in the input swaps exactly their scores.
    With card effects (EnvConfig.card_effects) a card's effects, after the piles, swap with it; with enemy statuses
    (EnvConfig.enemy_statuses) an enemy's block at the end swaps with it."""
    import torch as th
    from collab_agent.config import (A_PLAY0, N_TARGETS, HAND_SIZE, OFF_PLAYERS, PLAYER_SIZE, OFF_ENEMIES, ENEMY_SIZE, OFF_CARDS,
                                     CARD_SIZE, N_PLAYERS, OFF_PILES, N_PILES, PILE_SIZE, OBS_SIZE, OFF_EFFECTS, EFFECT_SIZE,
                                     N_CARD_SLOTS, N_ENEMIES, ENEMY_EXTRA_SIZE)
    x = th.as_tensor(obs)
    extra, eff, foe = x.shape[1] - OBS_SIZE, N_CARD_SLOTS * EFFECT_SIZE, N_ENEMIES * ENEMY_EXTRA_SIZE
    effects = extra in (eff, eff + foe)
    foes_at = OBS_SIZE + (eff if effects else 0) if extra in (foe, eff + foe) else None

    def swap(spans):
        y = x.clone()
        for a, b, size in spans:
            y[:, a:a + size], y[:, b:b + size] = x[:, b:b + size], x[:, a:a + size]
            if effects and OFF_CARDS <= a < OFF_PILES:                 # a card span: its effects too
                ea, eb = (OFF_EFFECTS + (off - OFF_CARDS) // CARD_SIZE * EFFECT_SIZE for off in (a, b))
                n = size // CARD_SIZE * EFFECT_SIZE
                y[:, ea:ea + n], y[:, eb:eb + n] = x[:, eb:eb + n], x[:, ea:ea + n]
            if foes_at is not None and OFF_ENEMIES <= a < OFF_CARDS:   # an enemy span: its extra statuses too
                fa, fb = (foes_at + (off - OFF_ENEMIES) // ENEMY_SIZE * ENEMY_EXTRA_SIZE for off in (a, b))
                n = size // ENEMY_SIZE * ENEMY_EXTRA_SIZE
                y[:, fa:fa + n], y[:, fb:fb + n] = x[:, fb:fb + n], x[:, fa:fa + n]
        return y

    def same_after(y, pairs):
        expected = base.clone()
        for i, j in pairs:
            expected[:, i], expected[:, j] = base[:, j], base[:, i]
        assert (policy.action_logits(y) - expected).abs().max() < 1e-4
        assert (policy.predict_values(y) - value).abs().max() < 1e-4

    play = lambda h, t: A_PLAY0 + N_TARGETS * h + t
    hand = HAND_SIZE * CARD_SIZE
    piles = N_PILES * PILE_SIZE
    with th.no_grad():
        base, value = policy.action_logits(x), policy.predict_values(x)
        same_after(swap([(OFF_PLAYERS + PLAYER_SIZE, OFF_PLAYERS + 2 * PLAYER_SIZE, PLAYER_SIZE), (OFF_CARDS + hand, OFF_CARDS + 2 * hand, hand),
                         (OFF_PILES + piles, OFF_PILES + 2 * piles, piles)]), [(play(h, 1), play(h, 2)) for h in range(HAND_SIZE)])
        same_after(swap([(OFF_CARDS, OFF_CARDS + CARD_SIZE, CARD_SIZE)]), [(play(0, t), play(1, t)) for t in range(N_TARGETS)])
        same_after(swap([(OFF_ENEMIES, OFF_ENEMIES + ENEMY_SIZE, ENEMY_SIZE)]), [(play(h, 4), play(h, 5)) for h in range(HAND_SIZE)])
        choice = OFF_CARDS + N_PLAYERS * hand
        same_after(swap([(choice, choice + CARD_SIZE, CARD_SIZE)]), [(A_CHOOSE0, A_CHOOSE0 + 1)])


def check_pair_training(cfg, team):
    """--network pair: trains every part it should, saves and loads the same, plays only legal moves, says so in its config."""
    import os, tempfile
    import torch as th
    from sb3_contrib import MaskablePPO
    from stable_baselines3.common.vec_env import DummyVecEnv
    import evaluate as EV
    from train import train, make_env
    from collab_agent.pair_policy import PairPolicy
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as out:
        path = train(cfg, 256, out, n_envs=2, seed=1, verbose=0)
        assert EV.load_config(path).network == "pair"
        model = MaskablePPO.load(path, device="cpu", env=DummyVecEnv([make_env(cfg, 2)]))
        assert isinstance(model.policy, PairPolicy) and model.policy.action_net.__class__.__name__ == "PairHead"
        before = {n: p.detach().clone() for n, p in model.policy.named_parameters()}
        model.learn(1024, reset_num_timesteps=False)
        still = [n for n, p in model.policy.named_parameters() if th.equal(p, before[n]) and "chooser" not in n]
        assert not still, f"not training: {still}"                      # the chooser only moves when a question came up
        again = os.path.join(out, "again")
        model.save(again)
        twin = MaskablePPO.load(again, device="cpu")
        env = CollabEnv(cfg, seed=3, fixed_team=team)
        act = EV.policy_model(twin)
        obs, _ = env.reset()
        batch, fights = [], 0
        while fights < 3:                                               # env is strict: an illegal move raises
            batch.append(obs.copy())
            obs, _, done, _, _ = env.step(int(act(env, obs)))
            if done:
                fights += 1
                obs, _ = env.reset()
        x = th.as_tensor(np.array(batch[:64]))
        with th.no_grad():
            assert th.equal(model.policy.action_logits(x), twin.policy.action_logits(x))
        check_pair_symmetry(twin.policy, np.array(batch[:64]))
        size = sum(p.numel() for p in twin.policy.parameters())
    return size, len(batch)


def test_pair_network():
    """--network pair on the mock engine; the default stays the flat network."""
    from train import build_config
    assert EnvConfig().network == "flat" and build_config().network == "flat"
    try:
        build_config(network="big")
        raise AssertionError("an unknown network must be refused")
    except ValueError:
        pass
    size, decisions = check_pair_training(build_config(network="pair", collab_w=(0, 0, 0), timesteps=256), ["aggressive", "defensive", "support"])
    print(f"ok  --network pair: {size:,} parameters, all parts train, saved and loaded the same, legal over {decisions} decisions, swapped seats, cards and enemies swap scores; off by default")


def test_sort_teammates(episodes=30):
    """--sort-teammates on the mock engine: masks stay legal, slot 1 is the most at risk, the reward still adds up."""
    assert EnvConfig().sort_teammates is False
    env = CollabEnv(EnvConfig(sort_teammates=True), seed=8)
    rng = np.random.default_rng(8)
    moved = 0
    for _ in range(episodes):
        env.reset()
        done = False
        while not done:
            c = env.combat
            alive = [s for s in env.slots[1:] if s < len(c.players) and c.players[s] is not None and c.players[s].alive]
            left = [c.players[s].hp - max(0, c.incoming(s) - c.players[s].block) for s in alive]
            assert left == sorted(left), left
            moved += env.slots != sorted(env.slots)
            _, _, done, _, _ = env.step(int(rng.choice(np.flatnonzero(env.action_masks()))))
    assert moved
    print(f"ok  --sort-teammates: {episodes} fights, masks legal, slot 1 most at risk ({moved} decisions not in seat order); off by default")


if __name__ == "__main__":
    test_teammates_option()
    test_blend_bot()
    test_continuous_bot_and_history()
    test_no_wait_and_blind()
    test_sort_teammates()
    test_pair_network()
    test_final_reward()
    test_reward_per_step()
    test_analyzer_history()
    test_swapped_profiles()
    test_characteristic_analyzer()
    test_divide_and_conquer()
    test_gym_api()
    test_random_rollouts()
