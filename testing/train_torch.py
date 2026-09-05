# -*- coding: utf-8 -*-
"""Train an agent to play simple.py, with PyTorch.

REINFORCE with a batch baseline. Solo by default: config.json supplies the
fight, but not the party size.

    python testing/train_torch.py              train, solo
    python testing/train_torch.py resume       continue from simple_agent.pt
    python testing/train_torch.py play         watch one fight
    python testing/train_torch.py --players 3  co-op
"""

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


import os
import sys

import numpy as np
import torch
import torch.nn as nn

from testing import config
from testing.simple import (SimpleEnv, battle, greedy, aggressive,
                            random_policy, ACTION_NAMES)

HERE = os.path.dirname(os.path.abspath(__file__))
SAVE_PATH = os.path.join(HERE, "simple_agent.pt")

N_ACT = 3
N_HIDDEN = 24
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def fight_kwargs(players=1, path=None):
    """simple.py's fight settings from config.json, forced to `players`.

    The config is the single source for HP, enemy damage and the turn limit
    so a UI can retune the fight without touching this file. Party size is
    the one thing it does NOT get to decide, because the trainer's default
    is a deliberate choice rather than a setting.
    """
    kw = config.simple_kwargs(config.load(path, quiet=True))
    kw["players"] = players
    return kw


class Policy(nn.Module):
    """obs -> 24 tanh -> 3 logits."""

    def __init__(self, n_obs, n_hidden=N_HIDDEN, n_act=N_ACT):
        super().__init__()
        self.n_obs = n_obs
        self.net = nn.Sequential(
            nn.Linear(n_obs, n_hidden),
            nn.Tanh(),
            nn.Linear(n_hidden, n_act),
        )

    def forward(self, obs, mask):
        """Logits with the illegal actions driven to -inf.

        Masking the LOGITS rather than the probabilities matters: zeroing a
        probability afterwards would leave log_prob at -inf and put a nan
        through the backward pass the first time an illegal action was
        sampled. -inf here simply makes softmax assign it exactly zero.
        """
        logits = self.net(obs)
        return logits.masked_fill(~mask, float("-inf"))

    def n_numbers(self):
        return sum(p.numel() for p in self.parameters())


def _obs_tensor(obs):
    return torch.as_tensor(np.asarray(obs, dtype=np.float32), device=DEVICE)


def run_episode(policy, env, seed=None, greedy_actions=False, max_steps=300):
    """Play one fight, returning the log-probs and rewards for each step."""
    obs = _obs_tensor(env.reset(seed=seed))
    logps, rewards = [], []
    done, steps = False, 0
    while not done and steps < max_steps:
        steps += 1
        mask = torch.as_tensor(env.legal_actions(), dtype=torch.bool,
                               device=DEVICE)
        logits = policy(obs, mask)
        dist = torch.distributions.Categorical(logits=logits)
        action = torch.argmax(logits) if greedy_actions else dist.sample()
        logps.append(dist.log_prob(action))
        nxt, reward, done, _ = env.step(int(action))
        rewards.append(reward)
        obs = _obs_tensor(nxt)
    return logps, rewards, env.engine.victory


def returns_to_go(rewards, gamma=0.99):
    """How much total reward followed each step."""
    out, running = [0.0] * len(rewards), 0.0
    for i in range(len(rewards) - 1, -1, -1):
        running = rewards[i] + gamma * running
        out[i] = running
    return out


def train(updates=400, batch=32, lr=0.02, seed=0, players=1, verbose=True,
          resume_from=None, config_path=None):
    """REINFORCE, with autograd computing the gradients."""
    torch.manual_seed(seed)
    kw = fight_kwargs(players, config_path)
    env = SimpleEnv(**kw)
    n_obs = env.observation_size()

    already = 0
    policy = Policy(n_obs).to(DEVICE)
    if resume_from and os.path.exists(resume_from):
        policy, already = load(resume_from, n_obs)
        if verbose:
            print("  resumed from {} ({} updates already done)".format(
                os.path.basename(resume_from), already))
    opt = torch.optim.Adam(policy.parameters(), lr=lr)

    rng = np.random.default_rng(seed + already)
    history = []
    for update in range(updates):
        batch_logps, batch_returns, wins = [], [], 0
        for _ in range(batch):
            logps, rewards, won = run_episode(
                policy, env, seed=int(rng.integers(1 << 30)))
            if not logps:
                continue
            wins += bool(won)
            batch_logps.append(torch.stack(logps))
            batch_returns.append(torch.as_tensor(
                returns_to_go(rewards), dtype=torch.float32, device=DEVICE))
        if not batch_logps:
            continue

        # One baseline over the whole batch, not a learned value head.
        flat = torch.cat(batch_returns)
        adv = (flat - flat.mean()) / (flat.std() + 1e-8)
        loss = -(torch.cat(batch_logps) * adv).sum() / batch

        opt.zero_grad()
        loss.backward()
        opt.step()

        rate = wins / batch
        history.append(rate)
        if verbose and (update % 40 == 0 or update == updates - 1):
            print("  update {:>4}/{}   win rate (last 20 batches) {:>5.1%}"
                  .format(update, updates, float(np.mean(history[-20:]))))

    return policy, history, already + updates


def save(policy, path, updates_done=0, players=1):
    torch.save({"state_dict": policy.state_dict(),
                "n_obs": policy.n_obs,
                "n_hidden": N_HIDDEN,
                "n_act": N_ACT,
                "players": players,
                "updates_done": updates_done}, path)


def load(path, expect_obs=None):
    """Returns (policy, updates_done), refusing a shape mismatch loudly."""
    blob = torch.load(path, map_location=DEVICE, weights_only=False)
    n_obs = blob["n_obs"]
    if expect_obs is not None and n_obs != expect_obs:
        raise ValueError(
            "saved agent expects {} observation floats but this setup has {} "
            "-- it was trained at {} player(s). Train fresh, or pass the "
            "matching --players.".format(n_obs, expect_obs,
                                         blob.get("players", "?")))
    policy = Policy(n_obs, blob["n_hidden"], blob["n_act"]).to(DEVICE)
    policy.load_state_dict(blob["state_dict"])
    return policy, int(blob.get("updates_done", 0))


def evaluate(policy, env, episodes=300, seed=12345):
    """Win rate on seeds the agent never trained on."""
    wins = 0
    with torch.no_grad():
        for i in range(episodes):
            _, _, won = run_episode(policy, env, seed=seed + i,
                                    greedy_actions=True)
            wins += bool(won)
    return wins / episodes


def baseline(policy_fn, kw, episodes=300, seed=12345):
    """The same seeds, played by a scripted policy, for comparison."""
    wins = sum(battle(policy_fn, seed=seed + i, **kw).won
               for i in range(episodes))
    return wins / episodes


def _players_arg(argv):
    if "--players" in argv:
        return max(1, min(4, int(argv[argv.index("--players") + 1])))
    return 1


def _main():
    argv = sys.argv[1:]
    players = _players_arg(argv)
    kw = fight_kwargs(players)

    if "play" in argv:
        if not os.path.exists(SAVE_PATH):
            print("No saved agent at {} -- run `python testing/train_torch.py`"
                  " first.".format(SAVE_PATH))
            return
        env = SimpleEnv(**kw)
        policy, done = load(SAVE_PATH, env.observation_size())
        print("Loaded {} numbers from {} ({} updates of training)".format(
            policy.n_numbers(), os.path.basename(SAVE_PATH), done))
        _watch(policy, env)
        return

    print("=" * 66)
    print("THE AGENT  (PyTorch {}, {})".format(torch.__version__, DEVICE))
    print("=" * 66)
    env = SimpleEnv(**kw)
    n_obs = env.observation_size()
    p = Policy(n_obs)
    print("  {} player(s): a {}->{}->{} network = {} numbers".format(
        players, n_obs, N_HIDDEN, N_ACT, p.n_numbers()))

    print()
    print("=" * 66)
    print("TRAINING")
    print("=" * 66)
    resume = SAVE_PATH if "resume" in argv else None
    policy, history, total = train(players=players, resume_from=resume)

    print()
    print("=" * 66)
    print("EVALUATION -- 300 fights on seeds never trained on")
    print("=" * 66)
    trained = evaluate(policy, SimpleEnv(**kw))
    print("  never blocks (aggressive)   {:>6.1%}".format(baseline(aggressive, kw)))
    print("  random                      {:>6.1%}".format(baseline(random_policy, kw)))
    print("  scripted greedy             {:>6.1%}".format(baseline(greedy, kw)))
    print("  TRAINED AGENT               {:>6.1%}".format(trained))

    save(policy, SAVE_PATH, updates_done=total, players=players)
    print()
    print("  saved to {} ({:,} bytes, {} updates total)".format(
        os.path.basename(SAVE_PATH), os.path.getsize(SAVE_PATH), total))



def _watch(policy, env):
    """Play one fight with the trained agent, narrating its choices."""
    obs = _obs_tensor(env.reset(seed=7))
    print()
    done, steps = False, 0
    with torch.no_grad():
        while not done and steps < 200:
            steps += 1
            mask = torch.as_tensor(env.legal_actions(), dtype=torch.bool,
                                   device=DEVICE)
            logits = policy(obs, mask)
            probs = torch.softmax(logits, dim=-1)
            action = int(torch.argmax(logits))
            p, e = env.player, env.enemy
            print("  you {:>2}/{} hp, {:>2} block | Dummy {:>2}/{} hp | "
                  "{:<9} (confidence {:.0%})".format(
                      p.hp, p.max_hp, p.block, e.hp, e.max_hp,
                      ACTION_NAMES[action], float(probs[action])))
            nxt, _, done, _ = env.step(action)
            obs = _obs_tensor(nxt)
    print()
    print("  {} in {} steps".format(
        "WON" if env.engine.victory else "LOST", steps))


if __name__ == "__main__":
    _main()
