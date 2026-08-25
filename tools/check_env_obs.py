# -*- coding: utf-8 -*-
"""What does env.py actually expose, before touching the enemy cap?

Three things worth knowing: is the observation a fixed size across player
counts, can a summoned enemy past slot 4 be seen or hit, and does the
observation say anything about the hand the action space indexes into.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
from entities import Player
import enemies as E
import cards as C
from cards import make_starter_deck
import env as ENV

print("MAX_ENEMIES: env =", ENV.MAX_ENEMIES,
      "| engine =", __import__("combat").CombatEngine.MAX_ENEMIES)
print()

print("observation length by player count:")
for n in (1, 2, 3, 4):
    e = ENV.CombatEnv(
        lambda n=n: [Player(f"P{i}", 80, 3, deck=make_starter_deck())
                     for i in range(n)],
        lambda: [E.make_nibbit()], seed=1)
    obs = e.reset()
    print(f"   {n} player(s): len(obs) = {len(obs)}")
print()

print("a fight that grows past 4 enemies (Phrog Parasite spawns 4 on death):")
e = ENV.CombatEnv(lambda: [Player("P", 200, 99, deck=make_starter_deck())],
                  lambda: [E.make_phrog_parasite()], seed=3)
e.reset()
eng = e.engine
boss = eng.enemies[0]
boss.hp = 1
p = e._current_player()
s = make_starter_deck()[0]
p.hand = [s]
p.energy = 99
eng.play_card(p, s, target=boss)
print(f"   enemies on the board now: {len(eng.enemies)}")
print(f"   alive: {len(eng.enemies_alive())}")
obs = e._observe()
print(f"   observation length: {len(obs)}  "
      f"(covers {ENV.MAX_ENEMIES} enemy slots)")
seen = min(len(eng.enemies), ENV.MAX_ENEMIES)
print(f"   enemies represented in the observation: {seen} of {len(eng.enemies)}")

# Can the agent target the ones past the cap?
p.hand = [make_starter_deck()[0]]
mask = e.legal_action_mask()
targetable = {t for slot in range(1)
              for t in range(ENV.MAX_ENEMIES)
              if mask[slot * ENV.MAX_ENEMIES + t] > 0}
print(f"   targetable enemy indices: {sorted(targetable)}")
alive_idx = [i for i, en in enumerate(eng.enemies) if en.alive]
print(f"   alive enemy indices:      {alive_idx}")
print(f"   UNREACHABLE: {sorted(set(alive_idx) - targetable)}")
print()

print("does the observation describe the hand the actions index into?")
e = ENV.CombatEnv(lambda: [Player("P", 80, 3, deck=make_starter_deck())],
                  lambda: [E.make_nibbit()], seed=1)
e.reset()
p = e._current_player()
o1 = e._observe().copy()
p.hand = [C.make_wound() for _ in range(5)]
o2 = e._observe().copy()
print(f"   hand replaced with 5 Wounds; observation changed: "
      f"{not np.array_equal(o1, o2)}")
