"""Evaluate a trained agent against each teammate type, and compare with baselines.

    python evaluate.py runs/collab_agent/final_model.zip
    python evaluate.py runs/collab_agent/final_model.zip --episodes 300 --baselines
    python evaluate.py --engine real --baselines --episodes 50      # the baselines on the real engine

Every team is played twice on the same fights: once with the teammates' true profiles, once
with each teammate's A, S, T swapped in the agent's input for the style furthest from theirs
(collab_agent/styles.py). The advantage point is the difference in score: above 0, the agent
plays better when it knows who its teammates really are. A policy that never reads the
profiles (random, the Cheese bot) gets exactly 0.
"""
import argparse
import dataclasses
import json
import os

import numpy as np

from collab_agent.config import EnvConfig, RewardWeights
from collab_agent.final_reward import (FinalRewardConfig, PenaltyWeights, CollabSettings, SCORINGS,
                                       advantage_point)
from collab_agent.env import CollabEnv
from collab_agent.bots import CheeseBot
from collab_agent import styles

TEAMS = {
    "2x aggressive": ["aggressive"] * 2,
    "2x defensive": ["defensive"] * 2,
    "2x cheese": ["cheese"] * 2,
    "2x random": ["random"] * 2,
    "2x change": ["change"] * 2,
    "2x support": ["support"] * 2,
    "aggr+def": ["aggressive", "defensive"],
    "aggr+def+support": ["aggressive", "defensive", "support"],
    "random mix": None,
    "2x blend": ["blend"] * 2,
    "2x continuous": ["continuous"] * 2,
    "2x scale": ["scale"] * 2,
    "2x now": ["now"] * 2,
    "2x self": ["self"] * 2,
    "2x team": ["team"] * 2,
}


def config_from_dict(d):
    known = EnvConfig.__dataclass_fields__
    d = {k: v for k, v in d.items() if k in known}          # skip old settings (e.g. beta)
    d["reward"] = RewardWeights(**d["reward"])
    d["teammate_types"] = tuple(d["teammate_types"])
    if "final" in d:
        f = d["final"]
        penalty = PenaltyWeights(**f["penalty"])
        try:
            penalty.check()
        except ValueError as error:                          # a run from before A + B + C + D = 100
            print(f"note: the run's penalty weights are no longer valid ({error}); scoring with the defaults")
            penalty = PenaltyWeights()
        d["final"] = FinalRewardConfig(penalty, CollabSettings(**f["collab"]), f["total_timesteps"])
    return EnvConfig(**d)


def load_config(model_path):
    for path in (os.path.join(os.path.dirname(model_path), "config.json"),
                 os.path.join(os.path.dirname(os.path.dirname(model_path)), "config.json")):
        if os.path.exists(path):
            with open(path) as f:
                return config_from_dict(json.load(f))
    return EnvConfig()


def policy_model(model):
    def act(env, obs):
        a, _ = model.predict(obs, action_masks=env.action_masks(), deterministic=True)
        return int(a)
    return act


def policy_random(rng):
    def act(env, obs):
        return int(rng.choice(np.flatnonzero(env.action_masks())))
    return act


def policy_cheese():
    bot = CheeseBot()

    def act(env, obs):
        return styles.cheese_action(env, bot)
    return act


def run(cfg, team, act, episodes, seed):
    """Play `episodes` fights; returns the averages and every fight's final score."""
    env = CollabEnv(cfg, seed=seed, fixed_team=team)
    env.set_ctime(cfg.final.total_timesteps)           # evaluation = end of training
    obs, _ = env.reset()
    res = []
    while len(res) < episodes:
        obs, r, done, _, info = env.step(act(env, obs))
        if done:
            res.append(info["episode_summary"])
            obs, _ = env.reset()
    mean = lambda k: float(np.mean([s.get(k, 0.0) for s in res]))
    out = {k: mean(k) for k in ("win", "ret", "rounds", "ally_hp_frac", "score", "assist_share")}
    out["general_penalty"] = mean("penalty")
    for name in SCORINGS:
        out[f"f_{name}"] = mean(f"f_{name}")
    out["scores"] = [s.get("score", 0.0) for s in res]
    return out


def run_with_advantage(cfg, team, make_act, episodes, seed, refs):
    """run() twice on the same fights, with true and with swapped profiles. make_act() gives a
    fresh policy each time. Adds `score_swapped` and `advantage`."""
    true = run(cfg, team, make_act(), episodes, seed)
    swapped = run(dataclasses.replace(cfg, swap_profiles=True, style_profiles=refs), team, make_act(),
                  episodes, seed)
    true["score_swapped"] = swapped["score"]
    true["advantage"] = advantage_point(true.pop("scores"), swapped["scores"])
    return true


def evaluate_model(model_path, episodes=500, seed=12345, team=None):
    """Used by experiments.py: one model on random-mix teams, with its advantage point."""
    from sb3_contrib import MaskablePPO
    cfg = load_config(model_path)
    model = MaskablePPO.load(model_path, device="cpu")
    return run_with_advantage(cfg, team, lambda: policy_model(model), episodes, seed, styles.load_or_make(cfg))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model", nargs="?", default=None, help="path to model .zip (omit to run only baselines)")
    ap.add_argument("--episodes", type=int, default=200)
    ap.add_argument("--baselines", action="store_true", help="also run random and Cheese-bot agents")
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--engine", default=None, choices=["mock", "real"],
                    help="play on this engine (default: the one the model trained on; mock without a model)")
    args = ap.parse_args()

    policies = {}                                      # name -> a function giving a fresh policy
    cfg = EnvConfig()
    if args.model:
        from sb3_contrib import MaskablePPO
        cfg = load_config(args.model)
        model = MaskablePPO.load(args.model, device="cpu")
        policies["agent"] = lambda: policy_model(model)
    if args.baselines or not args.model:
        policies["random"] = lambda: policy_random(np.random.default_rng(args.seed))
        policies["cheese bot"] = policy_cheese
    if args.engine:
        cfg = dataclasses.replace(cfg, engine=args.engine)
    refs = styles.load_or_make(cfg)

    print(f"{'team':18s}" + "".join(f"| {name:^36s}" for name in policies))
    print(f"{'':18s}" + "| win   ally_hp  rounds  score  advantage " * len(policies))
    for team_name, team in TEAMS.items():
        row = f"{team_name:18s}"
        for name, make_act in policies.items():
            r = run_with_advantage(cfg, team, make_act, args.episodes, args.seed, refs)
            row += (f"| {r['win']:.2f}   {r['ally_hp_frac']:.2f}   {r['rounds']:5.1f}  {r['score']:5.1f}"
                    f"  {r['advantage']:+7.2f}  ")
        print(row, flush=True)


if __name__ == "__main__":
    main()
