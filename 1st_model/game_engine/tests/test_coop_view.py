# -*- coding: utf-8 -*-
"""The co-op observation is egocentric: slot 0 is always ME."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import numpy as np

from game_engine.entities import Player, seed_content
from game_engine.cards import make_starter_deck, TargetMode
import game_engine.cards as C
import game_engine.enemies as E
import game_engine.env as ENV

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
    aligned = all(
        hp_at(obs, k + 1) == round(allies[k].hp / allies[k].max_hp, 4)
        for k in range(len(allies)))
    check(f"P{seat} acting -> ally k lines up with slot k+1", aligned, True)
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
    base = ENV.FIRST_CARD_ALLY_ACTION + 0 * ENV.MAX_ALLY_TARGETS
    offered = [t for t in range(ENV.MAX_ALLY_TARGETS) if m[base + t] > 0]
    check("mask offers only the living ally, by player row", offered, [2])
    check("...and never the caster's own row 0", m[base + 0], 0.0)
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
e5.active_player_idx = 99
obs = e5._observe()
check("no crash, and slot 0 falls back to seat 0", hp_at(obs, 0), 0.44)

print()
print("8. every ALLY card lands on the teammate that was CHOSEN")
# Three of the five used to call _ally_of() and always hit the lowest living
# seat, so the action space's whole ally axis was a no-op for them. Asserted
# on STATE, not on the log tail: Demonic Shield exhausts, so its last log
# line names the card, not the recipient.
from game_engine.entities import Player as _P, seed_content as _sc
from game_engine.combat import CombatEngine as _CE
from game_engine.cards import make_starter_deck as _deck, TargetMode as _TM
import game_engine.cards as _C

_pool = {}
for _nm in ("CARD_POOL_IRONCLAD", "COLORLESS_POOL"):
    for _f in getattr(_C, _nm, []):
        _c = _f() if callable(_f) else _f
        _pool[_c.name] = (_f, _c.target)
_ally_cards = sorted(n for n, (_, t) in _pool.items() if t == _TM.ALLY)
check("the ALLY cards are all still present", len(_ally_cards), 5)


def _snap(p):
    return (p.block, p.energy, p.hp,
            tuple(sorted((k.name, v) for k, v in p.statuses.items())))


_wrong = []
for _name in _ally_cards:
    for _want in (1, 2):
        _sc(3)
        _ps = [_P(f"P{i}", 80, 3, _deck()) for i in range(3)]
        _eng = _CE(_ps, [E.make_nibbit()], seed=3)
        _eng.start_player_turn()
        _card = _pool[_name][0]()
        _ps[0].hand = [_card]
        _ps[0].energy = 3
        _ps[0].block = 9
        _before = [_snap(p) for p in _ps]
        _eng.play_card(_ps[0], _card, ally_target=_ps[_want])
        _changed = {i for i in (1, 2) if _snap(_ps[i]) != _before[i]}
        if _changed != {_want}:
            _wrong.append(f"{_name}: asked P{_want}, changed {sorted(_changed)}")
check("ALLY cards affect the chosen teammate and only them", _wrong, [])

print()
print("9. The Ball's 'random ally' is actually random")
# It used to call _ally_of(), which returns the FIRST living teammate --
# indistinguishable from random at 2 players, and simply wrong at 3-4.
from collections import Counter as _Counter
_got = _Counter()
for _seed in range(300):
    _sc(_seed)
    _ps = [_P(f"P{i}", 80, 3, _deck()) for i in range(4)]
    _eng = _CE(_ps, [E.make_nibbit()], seed=_seed)
    _eng.start_player_turn()
    _card = _pool["The Ball"][0]()
    _ps[0].hand = [_card]
    _ps[0].energy = 3
    _eng.play_card(_ps[0], _card, target=_eng.enemies[0])
    for _p in _ps[1:]:
        if _card in _p.discard_pile:
            _got[_p.name] += 1
check("all three teammates receive it at least once",
      sorted(_got) == ["P1", "P2", "P3"], True)
# Loose bound: a first-living-seat regression gives 100/0/0, which this
# catches. Deliberately not a tight chi-square -- that would flake.
_share = min(_got.values()) / max(1, sum(_got.values()))
check("no teammate is starved (>15% each; uniform is 33%)",
      _share > 0.15, True)

print()
if FAILS:
    print(f"FAILURE: {len(FAILS)} check(s) failed")
    for f in FAILS:
        print("  - " + f)
    sys.exit(1)
print("all co-op view checks passed")
