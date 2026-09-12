# -*- coding: utf-8 -*-
"""Same seed, same fight, twice - and again in a fresh process."""
import json, random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))
from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy

def run(seed):
    allies = [create_ally("testally1", "p%d" % (i+1), rng=random.Random(seed))
              for i in range(2)]
    enemies = [create_enemy("dummy1", "e%d" % (i+1), rng=random.Random(seed))
               for i in range(2)]
    c = Combat(allies, enemies, rng=random.Random(seed))
    c.start()
    log = [c.to_dict()]
    for _ in range(6):
        for ally in allies:
            while ally.hand and not c.is_over():
                try:
                    c.play_card(ally, 0, target=enemies[0])
                except Exception as error:
                    log.append(str(error))
                    break
        if c.is_over():
            break
        c.end_player_turn()
        log.append(c.to_dict())
    return json.dumps(log, sort_keys=True, default=str)

a, b = run(1234), run(1234)
print("same seed twice, same process :", "IDENTICAL" if a == b else "DIFFERENT")
print("different seed differs        :", "yes" if run(1234) != run(9999) else "NO - suspicious")
print(len(a), "chars of state compared")
import hashlib
print("digest:", hashlib.sha256(a.encode()).hexdigest()[:32])

import sys as _sys
_sys.exit(0 if a == b and run(1234) != run(9999) else 1)
