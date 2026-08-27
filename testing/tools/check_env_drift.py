# -*- coding: utf-8 -*-
"""Does env.legal_action_mask agree with what CombatEngine will accept?

The mask re-implements the affordability check instead of calling
playable_cards(), so every gate added since it was written is invisible to
it. This asks the mask which plays are legal, then actually attempts them.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import game_engine.env as ENV
from game_engine.cards import CardType, TargetMode
import game_engine.cards as C

cases = []


def probe(label, hand_builder, energy=99):
    e = ENV.SpireEnv() if hasattr(ENV, "SpireEnv") else None
    return e


# Find the env class name.
env_cls = None
for name in dir(ENV):
    obj = getattr(ENV, name)
    if isinstance(obj, type) and hasattr(obj, "legal_action_mask"):
        env_cls = obj
        break
print("env class:", env_cls.__name__)

import game_engine.enemies as E
from game_engine.entities import Player
e = env_cls(lambda: [Player("P", 200, 99, deck=C.make_starter_deck())],
            lambda: [E.make_nibbit()])
e.reset()
engine = e.engine
p = e._current_player()

def mask_says_legal(card):
    m = e.legal_action_mask()
    slot = p.hand.index(card)
    return any(m[slot * ENV.MAX_ENEMIES + t] > 0
               for t in range(ENV.MAX_ENEMIES))

def engine_accepts(card):
    return card in engine.playable_cards(p)

trials = [
    ("Wound (unplayable status)", C.make_wound()),
    ("Injury (unplayable curse)", [f() for f in C.CURSE_POOL if f().name == "Injury"][0]),
    ("Clash with a non-Attack in hand",
     [f() for f in C.COLORLESS_POOL if f().name == "Clash"][0]),
]

print()
print(f"{'case':<40} {'mask':>6} {'engine':>8}  drift")
for label, card in trials:
    p.hand = [card]
    if label.startswith("Clash"):
        p.hand = [card, [c for c in C.make_starter_deck() if c.name == "Defend"][0]]
    p.energy = 99
    m, g = mask_says_legal(card), engine_accepts(card)
    print(f"{label:<40} {str(m):>6} {str(g):>8}  {'DRIFT' if m != g else ''}")

# Sloth cap
p.hand = [[mk() for mk in C.STATUS_CARDS if mk().name == "Sloth"][0]]
strikes = [C.make_starter_deck()[0] for _ in range(4)]
p.hand += strikes
p.energy = 99
for s in strikes[:3]:
    engine.play_card(p, s, target=engine.enemies[0])
m = mask_says_legal(strikes[3])
g = engine_accepts(strikes[3])
print(f"{'4th card under Sloth cap':<40} {str(m):>6} {str(g):>8}  {'DRIFT' if m != g else ''}")

print()
print("enemy visibility: env MAX_ENEMIES =", ENV.MAX_ENEMIES,
      "| engine cap =", engine.MAX_ENEMIES)
