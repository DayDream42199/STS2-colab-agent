# -*- coding: utf-8 -*-
"""The three things a real training loop needs that nothing else covers.

Found by probing the env the way a trainer drives it, rather than the way the
feature tests drive it:

  1. TERMINAL STATE WAS FARMABLE. Stepping a finished episode fell through and
     re-awarded the +10/-10 terminal bonus every time, so a rollout loop that
     ignored `done` collected unbounded reward from a won fight. Nothing
     crashed, which is what made it dangerous.
  2. NO TRUNCATION. An unbounded episode does not fail loudly -- it hangs the
     rollout collecting it. No non-terminating fight could actually be
     constructed (enemies gain Strength and eventually out-scale any fixed
     block), but "probably terminates" is not a bound.
  3. OLD GYM API. reset() -> obs and step() -> 4-tuple. Gymnasium and SB3
     need reset() -> (obs, info) and a 5-tuple with terminated/truncated
     separated.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import numpy as np

from game_engine.entities import Player
from game_engine.cards import make_starter_deck
import game_engine.enemies as E
import game_engine.env as ENV

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  [{'ok' if ok else 'FAIL'}] {label}: got {got!r}, want {want!r}")
    if not ok:
        FAILS.append(label)


def mk():
    return [Player("P", 80, 3, deck=make_starter_deck())]


def foe():
    return [E.make_nibbit()]


def run_to_end(e, cap=500):
    done, g = False, 0
    while not done and g < cap:
        g += 1
        m = e.legal_action_mask()
        _, _, done, info = e.step(int(np.flatnonzero(m > 0)[0]))
    return info


print("1. a finished episode is absorbing, not farmable")
e = ENV.CombatEnv(mk, foe, seed=3)
e.reset()
run_to_end(e)
after = [e.step(ENV.END_TURN_ACTION) for _ in range(10)]
check("10 steps past done earn zero reward",
      sum(r for _, r, _, _ in after), 0.0)
check("...and still report done", all(d for _, _, d, _ in after), True)
check("...and are flagged absorbing",
      all(i.get("absorbing") for _, _, _, i in after), True)
check("the winning step itself still paid out",
      e.engine.victory, True)

print()
print("2. truncation bounds the pathological case")
# max_turns is in TURNS. Set it to 1 so it fires on a fight that would
# otherwise run ~14 -- the cap itself is 200 in normal use.
e = ENV.CombatEnv(mk, foe, seed=3, max_turns=1)
e.reset()
info = run_to_end(e)
check("a 1-turn cap ends the episode", True, True)
check("...flagged as truncated", info.get("truncated"), True)
check("...and the fight was NOT actually over",
      e.engine.is_over, False)

# Truncation must not pay the terminal bonus: the fight was cut short, it was
# neither won nor lost.
e2 = ENV.CombatEnv(mk, foe, seed=3, max_turns=1)
e2.reset()
rewards = []
done, g = False, 0
while not done and g < 200:
    g += 1
    m = e2.legal_action_mask()
    _, r, done, _ = e2.step(int(np.flatnonzero(m > 0)[0]))
    rewards.append(r)
check("no +/-10 terminal bonus on truncation",
      any(abs(r) >= 9.0 for r in rewards), False)

# The default must be generous enough never to fire in real play.
e3 = ENV.CombatEnv(mk, foe, seed=3)
check("default cap is 200 turns", e3.max_turns, 200)
e3.reset()
info = run_to_end(e3)
check("a normal fight never truncates", info.get("truncated"), False)
check("...and takes far fewer turns than the cap",
      e3.engine.turn_number < 60, True)

e4 = ENV.CombatEnv(mk, foe, seed=3, max_turns=None)
e4.reset()
info = run_to_end(e4)
check("max_turns=None disables truncation", info.get("truncated"), False)

print()
print("3. the Gymnasium adapter")
g = ENV.GymnasiumEnv(mk, foe, seed=5)
out = g.reset()
check("reset() returns (obs, info)", isinstance(out, tuple) and len(out) == 2, True)
obs, info = out
check("obs is the right shape", obs.shape, (ENV.OBS_SIZE,))
check("info carries an action_mask", "action_mask" in info, True)

step_out = g.step(ENV.END_TURN_ACTION)
check("step() returns a 5-tuple", len(step_out), 5)
o, r, term, trunc, i = step_out
check("terminated is a bool", isinstance(term, bool), True)
check("truncated is a bool", isinstance(trunc, bool), True)
check("action_masks() is bool dtype", g.action_masks().dtype == bool, True)
check("action_masks() length matches the action space",
      len(g.action_masks()), ENV.END_TURN_ACTION + 1)
check("render() returns text", isinstance(g.render(), str), True)
check("close() is callable", g.close(), None)
check("delegates unknown attrs to CombatEnv",
      g.observation_space_size(), ENV.OBS_SIZE)

# terminated and truncated must be mutually exclusive, and separated.
g2 = ENV.GymnasiumEnv(mk, foe, seed=3)
g2.reset()
term = trunc = False
for _ in range(500):
    m = g2.action_masks()
    _, _, term, trunc, _ = g2.step(int(np.flatnonzero(m)[0]))
    if term or trunc:
        break
check("a won fight is terminated, not truncated", (term, trunc), (True, False))

g3 = ENV.GymnasiumEnv(mk, foe, seed=3, max_turns=1)
g3.reset()
term = trunc = False
for _ in range(500):
    m = g3.action_masks()
    _, _, term, trunc, _ = g3.step(int(np.flatnonzero(m)[0]))
    if term or trunc:
        break
check("a capped fight is truncated, not terminated", (term, trunc), (False, True))

print()
print("4. the old API is untouched (every other caller depends on it)")
e = ENV.CombatEnv(mk, foe, seed=1)
obs = e.reset()
check("reset() still returns a bare array", isinstance(obs, np.ndarray), True)
check("step() still returns a 4-tuple", len(e.step(ENV.END_TURN_ACTION)), 4)

print()
if FAILS:
    print(f"FAILURE: {len(FAILS)} check(s) failed")
    for f in FAILS:
        print("  - " + f)
    sys.exit(1)
print("all training-API checks passed")
