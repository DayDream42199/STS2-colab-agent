# -*- coding: utf-8 -*-
"""Player state must not leak between combats."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from game_engine.entities import Player, seed_content
from game_engine.cards import make_starter_deck
from game_engine.combat import CombatEngine
from game_engine.relics import BURNING_BLOOD
import game_engine.enemies as E

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  [{'ok' if ok else 'FAIL'}] {label}: got {got!r}, want {want!r}")
    if not ok:
        FAILS.append(label)


PERSISTS_ACROSS_COMBATS = {
    "name", "max_hp", "max_energy",
    "deck_template",
    "relics", "relic_counters",
    "potions", "potion_slots",
    "rng",
    "engine",
    "draw_pile",
}

RESET_BY_START_TURN = {
    "energy", "cards_played_this_turn", "skills_played_this_turn",
}


def fresh_player():
    seed_content(0)
    p = Player("Ironclad", 80, 3, deck=make_starter_deck())
    p.add_relic(BURNING_BLOOD)
    return p


def snapshot(p):
    """Value-copy of every instance field, so later mutation can't alias it."""
    out = {}
    for k, v in vars(p).items():
        out[k] = list(v) if isinstance(v, list) else (
            dict(v) if isinstance(v, dict) else (
                set(v) if isinstance(v, set) else v))
    return out


def _structured_poison():
    from game_engine.cards import make_starter_deck as _deck
    card = _deck()[0]
    return {
        "temp_cost_cards": [(card, "combat")],
        "temp_replay_cards": [card],
        "temp_upgrades": [card],
    }


def poison(p, skip):
    """Give every resettable field an obviously-wrong value."""
    changed = []
    structured = _structured_poison()
    for k, v in list(vars(p).items()):
        if k in skip:
            continue
        if k in structured:
            setattr(p, k, structured[k])
            changed.append(k)
            continue
        if isinstance(v, bool):
            new = not v
        elif isinstance(v, int):
            new = v + 77
        elif isinstance(v, float):
            new = v + 7.5
        elif isinstance(v, list):
            new = ["POISON"]
        elif isinstance(v, set):
            new = {"POISON"}
        elif isinstance(v, dict):
            new = {"POISON": 1}
        else:
            continue
        setattr(p, k, new)
        changed.append(k)
    return changed


print("1. start_combat() restores every per-combat field")
p = fresh_player()
before = snapshot(p)
touched = poison(p, PERSISTS_ACROSS_COMBATS)
p.start_combat(seed=1)
after = snapshot(p)
leaked = sorted(k for k in touched
                if k not in RESET_BY_START_TURN and after[k] != before[k])
check(f"{len(touched)} poisoned fields, none leaking past start_combat",
      leaked, [])

print()
print("2. start_turn() restores the fields start_combat() leaves alone")
p2 = fresh_player()
base = snapshot(p2)
p2.start_combat(seed=1)
for k in RESET_BY_START_TURN:
    setattr(p2, k, getattr(p2, k) + 77)
p2.start_turn()
still = sorted(k for k in RESET_BY_START_TURN if getattr(p2, k) != base[k])
check("turn-scoped allowlist really is reset by start_turn", still, [])

print()
print("3. no field is born late (must exist from __init__ onward)")
p3 = fresh_player()
at_init = set(vars(p3))
p3.start_combat(seed=1)
after_combat = set(vars(p3))
check("start_combat() introduces no new attribute",
      sorted(after_combat - at_init), [])
p3.start_turn()
check("start_turn() introduces no new attribute",
      sorted(set(vars(p3)) - at_init), [])

print()
print("4. the allowlists themselves are not stale")
real = set(vars(fresh_player()))
check("every PERSISTS_ACROSS_COMBATS name is a real field",
      sorted(PERSISTS_ACROSS_COMBATS - real), [])
check("every RESET_BY_START_TURN name is a real field",
      sorted(RESET_BY_START_TURN - real), [])
check("the two allowlists do not overlap",
      sorted(PERSISTS_ACROSS_COMBATS & RESET_BY_START_TURN), [])

print()
print("5. a real fight leaves nothing behind for the next one")
p4 = fresh_player()
clean = snapshot(p4)
eng = CombatEngine([p4], [E.make_nibbit()], seed=2)
eng.start_player_turn()
turns = 0
while not eng.is_over and turns < 40:
    turns += 1
    for card in list(eng.playable_cards(p4)):
        eng.play_card(p4, card, target=eng.enemies_alive()[0] if eng.enemies_alive() else None)
    eng.end_player_turn()
    if not eng.is_over:
        eng.run_enemy_turn()
    if not eng.is_over:
        eng.start_player_turn()
check("the fight actually ran", turns > 0 and p4.cards_played_this_combat > 0, True)

p4.start_combat(seed=3)
p4.start_turn()
dirty = snapshot(p4)
skip = PERSISTS_ACROSS_COMBATS | {
    "hand", "discard_pile", "cards_drawn_this_turn", "cards_drawn_this_combat",
    "exhaust_pile", "energy",
}
leaked = sorted(k for k in clean if k not in skip and dirty[k] != clean[k])
check("no combat-1 state survives into combat 2", leaked, [])

print()
if FAILS:
    print(f"FAILURE: {len(FAILS)} check(s) failed")
    for f in FAILS:
        print("  - " + f)
    sys.exit(1)
print("all state-drift checks passed")
