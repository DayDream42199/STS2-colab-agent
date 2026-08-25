# -*- coding: utf-8 -*-
"""The co-op observation is egocentric: slot 0 is always ME.

WHAT THIS GUARDS. The observation used to list players by seat, so player
slot 0 held P0's HP no matter who was acting. A single shared policy -- the
normal way to train co-op -- therefore could not tell its own HP from a
teammate's, and would learn to block based on whichever seat happened to be
first.

It was also internally inconsistent, which is the sharper bug: the relic,
potion, pile and hand sections have ALWAYS described the acting player, so
the vector showed one player's hand next to another player's HP.

The fix rotates the player block so the actor is slot 0 and teammates follow
in wrapped seat order. Ally target indices count over the same order, so ally
action k names player slot k+1 -- checked here, because rotating the
observation while leaving targeting in seat order would just move the bug.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np

from entities import Player, seed_content
from cards import make_starter_deck, TargetMode
import cards as C
import enemies as E
import env as ENV

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  [{'ok' if ok else 'FAIL'}] {label}: got {got!r}, want {want!r}")
    if not ok:
        FAILS.append(label)


P_OFF = ENV.OBS_OFFSETS["players"][0]
EF = ENV.ENTITY_FEATURES


def hp_at(obs, slot):
    """Normalised HP the observation reports for player slot `slot`."""
    return round(float(obs[P_OFF + slot * EF]), 4)


def bag(hp=4000):
    e = E.make_nibbit()
    e.max_hp = e.hp = hp
    return e


def party(n, hps):
    def build():
        out = []
        for i in range(n):
            p = Player(f"P{i}", 100, 3, deck=make_starter_deck())
            p.hp = hps[i]
            out.append(p)
        return out
    return build


print("1. slot 0 is the ACTING player, not seat 0")
# Distinct HP per player, so a slot's occupant is unambiguous.
HPS = [40, 60, 80, 100]
e = ENV.CombatEnv(party(4, HPS), lambda: [bag()], seed=1)
e.reset()
for p, hp in zip(e.engine.players, HPS):
    p.hp = hp

for seat in range(4):
    e.active_player_idx = seat
    obs = e._observe()
    check(f"P{seat} acting -> slot 0 shows P{seat}'s HP",
          hp_at(obs, 0), round(HPS[seat] / 100.0, 4))

print()
print("2. teammates follow in WRAPPED seat order")
e.active_player_idx = 2
obs = e._observe()
check("P2 acting -> slots are [P2, P3, P0, P1]",
      [hp_at(obs, s) for s in range(4)],
      [round(HPS[i] / 100.0, 4) for i in (2, 3, 0, 1)])

print()
print("3. the rest of the vector already described the actor -- now consistent")
e2 = ENV.CombatEnv(party(2, [30, 90]), lambda: [bag()], seed=2)
e2.reset()
e2.engine.players[0].hp, e2.engine.players[1].hp = 30, 90
for seat in (0, 1):
    e2.active_player_idx = seat
    obs = e2._observe()
    me = e2._current_player()
    check(f"P{seat} acting -> slot-0 HP matches _current_player()",
          hp_at(obs, 0), round(me.hp / me.max_hp, 4))

print()
print("4. ally action k names player slot k+1")
# Give every player an ally-targeting card so the mask has ALLY entries.
def blaze_party():
    out = []
    for i in range(3):
        deck = make_starter_deck()
        for f in C.COLORLESS_POOL:
            c = f()
            if c.name == "Lift":
                deck.append(f())
                break
        p = Player(f"P{i}", 100, 3, deck=deck)
        out.append(p)
    return out


e3 = ENV.CombatEnv(blaze_party, lambda: [bag()], seed=4)
e3.reset()
HP3 = [25, 55, 85]
for p, hp in zip(e3.engine.players, HP3):
    p.hp = hp

for seat in range(3):
    e3.active_player_idx = seat
    obs = e3._observe()
    allies = e3._allies_in_obs_order()
    # Every ally index must match the player the observation puts at k+1.
    aligned = all(
        hp_at(obs, k + 1) == round(allies[k].hp / allies[k].max_hp, 4)
        for k in range(len(allies)))
    check(f"P{seat} acting -> ally k lines up with slot k+1", aligned, True)
    # And _ally_at must resolve to that same player.
    check(f"P{seat} acting -> _ally_at(0) is the slot-1 player",
          e3._ally_at(0) is allies[0], True)

print()
print("5. a dead ally keeps its slot but is not targetable")
e3.active_player_idx = 0
allies = e3._allies_in_obs_order()
allies[0].hp = 0
allies[0].alive = False
obs = e3._observe()
check("the downed ally still occupies slot 1 (mapping does not shift)",
      hp_at(obs, 1), 0.0)
check("_ally_at(0) falls through to a LIVING ally",
      e3._ally_at(0) is allies[1], True)

# The mask must not offer the dead one.
me = e3._current_player()
lift = None
for c in me.draw_pile + me.hand:
    if c.target == TargetMode.ALLY:
        lift = c
        break
if lift is not None:
    me.hand = [lift]
    me.energy = 3
    m = e3.legal_action_mask()
    offered = [t for t in range(len(allies)) if m[0 * ENV.MAX_ENEMIES + t] > 0]
    check("mask offers only the living ally index", offered, [1])
else:
    print("  [skip] no ALLY card available in this deck")

print()
print("6. solo play is unaffected")
e4 = ENV.CombatEnv(party(1, [70]), lambda: [bag()], seed=6)
obs = e4.reset()
e4.engine.players[0].hp = 70
obs = e4._observe()
check("single player sits at slot 0", hp_at(obs, 0), 0.7)
check("slots 1-3 stay zero-padded",
      [hp_at(obs, s) for s in (1, 2, 3)], [0.0, 0.0, 0.0])

print()
print("7. an out-of-range actor index falls back to seat order")
e5 = ENV.CombatEnv(party(2, [44, 88]), lambda: [bag()], seed=7)
e5.reset()
e5.engine.players[0].hp, e5.engine.players[1].hp = 44, 88
e5.active_player_idx = 99          # past the party, as it is after a defeat
obs = e5._observe()
check("no crash, and slot 0 falls back to seat 0", hp_at(obs, 0), 0.44)

print()
if FAILS:
    print(f"FAILURE: {len(FAILS)} check(s) failed")
    for f in FAILS:
        print("  - " + f)
    sys.exit(1)
print("all co-op view checks passed")
