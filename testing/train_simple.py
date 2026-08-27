# -*- coding: utf-8 -*-
"""Train an agent to play simple.py. Pure numpy -- no torch, no gym.

WHAT AN "AI" ACTUALLY IS HERE: a bag of numbers. This one is 7x24 + 24x3
weights and their biases -- 267 numbers total. Training means nudging those
numbers until the actions they produce win more often. When we "save the
model" we are saving that array to a .npz file. That is the whole mystery.

WHERE IT TRAINS: right here, in this process, on your CPU. No GPU, no cloud,
no server. The loop is:

    play a batch of games  ->  see which actions preceded good outcomes
    ->  nudge the numbers toward those actions  ->  repeat

WHERE IT IS STORED: simple_agent.npz, next to this file. Delete it and you
have deleted the agent; copy it and you have copied the agent.

    python train_simple.py            # train fresh, evaluate, save
    python train_simple.py resume     # continue training the saved agent
    python train_simple.py play       # load the saved agent and watch it
"""

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


import os
import sys

import numpy as np

from testing.simple import (SimpleEnv, battle, greedy, aggressive, random_policy,
                    PLAY_STRIKE, PLAY_DEFEND, END_TURN, ACTION_NAMES)

HERE = os.path.dirname(os.path.abspath(__file__))
SAVE_PATH = os.path.join(HERE, "simple_agent.npz")

N_OBS = 7          # see SimpleEnv._observe
N_ACT = 3          # strike / defend / end turn
N_HIDDEN = 24


# ---------------------------------------------------------------------------
# The policy: obs -> probability of each action
# ---------------------------------------------------------------------------

class Policy(object):
    """A two-layer network. 267 numbers, and that is the entire agent.

    obs(7) -> tanh(hidden 24) -> logits(3) -> softmax -> pick an action.

    Deliberately tiny. The point is that you can print every number in it,
    and that it trains to convergence in under a minute on a laptop CPU."""

    def __init__(self, rng=None):
        rng = rng or np.random.default_rng(0)
        # Small random starting values. Not zeros -- if every weight were
        # identical, every hidden unit would compute the same thing forever.
        self.w1 = rng.normal(0, 0.5, (N_OBS, N_HIDDEN))
        self.b1 = np.zeros(N_HIDDEN)
        self.w2 = rng.normal(0, 0.5, (N_HIDDEN, N_ACT))
        self.b2 = np.zeros(N_ACT)

    def params(self):
        return [self.w1, self.b1, self.w2, self.b2]

    def forward(self, obs, mask):
        """Returns (probabilities, hidden) for one observation.

        `mask` is the legal-action mask. Illegal actions get -inf logits, so
        softmax gives them probability zero and the agent can NEVER pick one.
        That is why the env never sees an illegal action from a trained
        agent -- it is impossible, not merely unlikely."""
        hidden = np.tanh(obs @ self.w1 + self.b1)
        logits = hidden @ self.w2 + self.b2
        logits = np.where(mask, logits, -1e9)
        logits = logits - logits.max()               # stability
        exp = np.exp(logits)
        return exp / exp.sum(), hidden

    def save(self, path, updates_done=0):
        """`updates_done` rides along so a resumed run can report total
        training rather than restarting the count at zero."""
        np.savez(path, w1=self.w1, b1=self.b1, w2=self.w2, b2=self.b2,
                 updates_done=np.array(updates_done))

    @classmethod
    def load(cls, path):
        """Returns (policy, updates_done). Older files without the counter
        report 0 rather than failing."""
        d = np.load(path)
        p = cls()
        p.w1, p.b1, p.w2, p.b2 = d["w1"], d["b1"], d["w2"], d["b2"]
        done = int(d["updates_done"]) if "updates_done" in d.files else 0
        # Shape check: a saved file from a different N_HIDDEN cannot be
        # resumed into this network, and silently broadcasting would produce
        # nonsense rather than an error.
        if p.w1.shape != (N_OBS, N_HIDDEN) or p.w2.shape != (N_HIDDEN, N_ACT):
            raise ValueError(
                "saved agent is {}->{}->{} but this file expects {}->{}->{}; "
                "change N_HIDDEN or train fresh".format(
                    p.w1.shape[0], p.w1.shape[1], p.w2.shape[1],
                    N_OBS, N_HIDDEN, N_ACT))
        return p, done

    def n_numbers(self):
        return sum(a.size for a in self.params())


# ---------------------------------------------------------------------------
# Playing one game
# ---------------------------------------------------------------------------

def run_episode(policy, env, rng, seed=None, greedy_actions=False):
    """Play one fight. Returns the trajectory we need in order to learn.

    We record, for every step: what we saw, what was legal, what we did, and
    what reward followed. That is all REINFORCE needs."""
    obs = np.array(env.reset(seed=seed), dtype=np.float64)
    obs_log, hid_log, act_log, mask_log, rew_log = [], [], [], [], []

    done = False
    steps = 0
    while not done and steps < 300:
        steps += 1
        mask = np.array(env.legal_actions(), dtype=bool)
        probs, hidden = policy.forward(obs, mask)
        if greedy_actions:
            action = int(np.argmax(probs))
        else:
            action = int(rng.choice(N_ACT, p=probs))

        nxt, reward, done, _ = env.step(action)

        obs_log.append(obs)
        hid_log.append(hidden)
        act_log.append(action)
        mask_log.append(mask)
        rew_log.append(reward)
        obs = np.array(nxt, dtype=np.float64)

    return (np.array(obs_log), np.array(hid_log), np.array(act_log),
            np.array(mask_log), np.array(rew_log), env.engine.victory)


def returns_to_go(rewards, gamma=0.99):
    """How much total reward followed each step.

    An action is judged by everything that came AFTER it, not by the tiny
    reward it earned immediately -- that is what lets 'block now' get credit
    for 'survived to win six turns later'."""
    out = np.zeros_like(rewards, dtype=np.float64)
    running = 0.0
    for i in range(len(rewards) - 1, -1, -1):
        running = rewards[i] + gamma * running
        out[i] = running
    return out


# ---------------------------------------------------------------------------
# The training loop
# ---------------------------------------------------------------------------

def train(updates=400, batch=32, lr=0.02, seed=0, verbose=True,
          resume_from=None):
    """REINFORCE: play games, then push the numbers toward whatever preceded
    good outcomes and away from whatever preceded bad ones.

    The gradient for a softmax policy is beautifully simple: for the action
    you took, (1 - prob); for the others, (0 - prob); scaled by how good the
    outcome was. That is the `advantage * (onehot - probs)` line below.

    RESUMING: pass `resume_from` a .npz path and training continues from
    those weights instead of fresh random ones. Nothing else needs to change
    -- REINFORCE keeps no optimiser state between updates (no momentum, no
    running averages), so the weights ARE the entire checkpoint. That is not
    true of Adam-based training, where resuming without the optimiser state
    gives you a visible dip before it recovers.

    The rng seed is deliberately advanced on resume, so a second run does not
    replay the identical 12,800 games the first run already learned from.
    """
    rng = np.random.default_rng(seed)
    already = 0
    if resume_from and os.path.exists(resume_from):
        policy, already = Policy.load(resume_from)
        # Fresh games for the continued run.
        rng = np.random.default_rng(seed + already + 1)
        if verbose:
            print("  resumed from {} ({} updates already done)".format(
                os.path.basename(resume_from), already))
    else:
        policy = Policy(np.random.default_rng(seed))
    env = SimpleEnv()
    history = []

    for update in range(updates):
        grads = [np.zeros_like(p) for p in policy.params()]
        all_returns, wins = [], 0

        episodes = []
        for i in range(batch):
            # A fresh seed per episode: the agent must learn to play the
            # GAME, not memorise one shuffle.
            ep = run_episode(policy, env, rng, seed=int(rng.integers(1 << 30)))
            episodes.append(ep)
            wins += bool(ep[5])
            all_returns.append(returns_to_go(ep[4]))

        # Baseline: subtract the average return so we reinforce "better than
        # usual" rather than "positive". Without it, every action in a winning
        # game looks good, including the bad ones.
        flat = np.concatenate(all_returns)
        mean, std = flat.mean(), flat.std() + 1e-8

        for (obs_log, hid_log, act_log, mask_log, _rew), ret in zip(
                [e[:5] for e in episodes], all_returns):
            adv = (ret - mean) / std
            for t in range(len(act_log)):
                probs, _ = policy.forward(obs_log[t], mask_log[t])
                onehot = np.zeros(N_ACT)
                onehot[act_log[t]] = 1.0
                dlogits = adv[t] * (onehot - probs)

                # Backprop by hand -- two layers is small enough that the
                # chain rule is more readable than an autograd dependency.
                h = hid_log[t]
                grads[2] += np.outer(h, dlogits)        # d/d w2
                grads[3] += dlogits                     # d/d b2
                dh = (policy.w2 @ dlogits) * (1 - h * h)   # tanh' = 1 - tanh^2
                grads[0] += np.outer(obs_log[t], dh)    # d/d w1
                grads[1] += dh                          # d/d b1

        for p, g in zip(policy.params(), grads):
            p += lr * g / batch          # ascend: we want MORE reward

        rate = wins / batch
        history.append(rate)
        if verbose and (update % 40 == 0 or update == updates - 1):
            recent = np.mean(history[-20:])
            print("  update {:>4}/{}   win rate (last 20 batches) {:>5.1%}"
                  .format(update, updates, recent))

    return policy, history, already + updates


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate(policy, episodes=300, seed=12345):
    """Win rate on seeds the agent never trained on."""
    rng = np.random.default_rng(seed)
    env = SimpleEnv()
    wins = 0
    for i in range(episodes):
        _, _, _, _, _, won = run_episode(policy, env, rng, seed=seed + i,
                                         greedy_actions=True)
        wins += bool(won)
    return wins / episodes


def baseline(policy_fn, episodes=300, seed=12345):
    """The same seeds, played by a scripted policy, for comparison."""
    wins = sum(battle(policy_fn, seed=seed + i).won for i in range(episodes))
    return wins / episodes


def _main():
    if "play" in sys.argv:
        if not os.path.exists(SAVE_PATH):
            print("No saved agent at {} -- run `python train_simple.py` first."
                  .format(SAVE_PATH))
            return
        policy, done = Policy.load(SAVE_PATH)
        print("Loaded {} numbers from {} ({} updates of training)".format(
            policy.n_numbers(), os.path.basename(SAVE_PATH), done))
        _watch(policy)
        return

    print("=" * 66)
    print("THE AGENT")
    print("=" * 66)
    p = Policy()
    print("  a {}->{}->{} network = {} numbers".format(
        N_OBS, N_HIDDEN, N_ACT, p.n_numbers()))
    print("  that array IS the agent. Training changes those numbers.")

    print()
    print("=" * 66)
    print("TRAINING (on your CPU, in this process)")
    print("=" * 66)
    resume = SAVE_PATH if "resume" in sys.argv else None
    policy, history, total = train(resume_from=resume)

    print()
    print("=" * 66)
    print("EVALUATION -- 300 fights on seeds never trained on")
    print("=" * 66)
    trained = evaluate(policy)
    print("  never blocks (aggressive)   {:>6.1%}".format(baseline(aggressive)))
    print("  random                      {:>6.1%}".format(baseline(random_policy)))
    print("  scripted greedy             {:>6.1%}".format(baseline(greedy)))
    print("  TRAINED AGENT               {:>6.1%}".format(trained))

    policy.save(SAVE_PATH, updates_done=total)
    size = os.path.getsize(SAVE_PATH)
    print()
    print("  saved to {} ({:,} bytes, {} updates total)".format(
        os.path.basename(SAVE_PATH), size, total))
    print("  that file is the agent. `python train_simple.py play` to watch it.")


def _watch(policy):
    """Play one fight with the trained agent, narrating its choices."""
    rng = np.random.default_rng(0)
    env = SimpleEnv()
    obs = np.array(env.reset(seed=7), dtype=np.float64)
    print()
    done, steps = False, 0
    while not done and steps < 200:
        steps += 1
        mask = np.array(env.legal_actions(), dtype=bool)
        probs, _ = policy.forward(obs, mask)
        action = int(np.argmax(probs))
        p, e = env.player, env.enemy
        print("  you {:>2}/{} hp, {:>2} block | Dummy {:>2}/{} hp | "
              "{:<9} (confidence {:.0%})".format(
                  p.hp, p.max_hp, p.block, e.hp, e.max_hp,
                  ACTION_NAMES[action], probs[action]))
        nxt, _, done, _ = env.step(action)
        obs = np.array(nxt, dtype=np.float64)
    print()
    print("  {} in {} steps".format(
        "WON" if env.engine.victory else "LOST", steps))


if __name__ == "__main__":
    _main()
