# -*- coding: utf-8 -*-
"""Play whole fights with random decks from the whole registry.

Legal refusals (ValueError / IndexError / RuntimeError - the types Session
catches and turns into a private error) are expected and tallied. Anything
else escaping Combat is a bug.
"""
import json, random, sys, traceback, collections
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))
from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy, known_enemy_type_ids
from GameEngine.Registry.card_registry import create_card, known_card_ids
from GameEngine.Cards._card_enums import TargetType

ALL = known_card_ids()
ENEMIES = known_enemy_type_ids()
REFUSAL = (ValueError, IndexError, RuntimeError)

def one_fight(seed, ask_players, turns=12, deck_size=15):
    rng = random.Random(seed)
    allies = [create_ally("testally1", "p%d" % (i + 1), rng=random.Random(seed + i))
              for i in range(2)]
    for a in allies:
        a.deck = [rng.choice(ALL) for _ in range(deck_size)]
        a.max_hp = a.current_hp = 300
    # Mixed lineups from everything registered: a boss next to a slime is not
    # a real encounter, but every pairing has to survive.
    enemies = [create_enemy(rng.choice(ENEMIES), "e%d" % (i + 1), rng=random.Random(seed + 10 + i))
               for i in range(rng.randint(1, 3))]
    c = Combat(allies, enemies, rng=random.Random(seed))
    c.ask_players = ask_players
    c.start()
    for e in enemies:
        e.current_hp = e.max_hp = 120
    refusals = collections.Counter()
    plays = answers = 0

    def answer_all():
        nonlocal answers
        guard = 0
        while c.pending_choices and guard < 50:
            guard += 1
            uid, ask = next(iter(c.pending_choices.items()))
            ally = c.find_unit(uid)
            c.answer_choice(ally, rng.randrange(len(ask.options)))
            answers += 1

    for _ in range(turns):
        if c.is_over():
            break
        json.dumps(c.to_dict())                     # serialization every turn
        for ally in allies:
            if not ally.is_alive():
                continue
            for _attempt in range(8):
                answer_all()                        # may empty the hand
                if c.is_over() or not ally.hand or not ally.is_alive():
                    break
                idx = rng.randrange(len(ally.hand))
                card = create_card(ally.hand[idx])
                target = None
                living_e = [e for e in enemies if e.is_alive()]
                living_a = [a for a in allies if a.is_alive() and a is not ally]
                if card.target_type is TargetType.ENEMY and living_e:
                    target = rng.choice(living_e)
                elif card.target_type is TargetType.ALLY and living_a:
                    target = rng.choice(living_a)
                try:
                    c.play_card(ally, idx, target=target)
                    plays += 1
                except REFUSAL as e:
                    refusals[str(e)] += 1
        answer_all()
        if c.is_over():
            break
        c.end_player_turn()
        answer_all()
    json.dumps(c.to_dict())
    return plays, answers, refusals, c


modes = ((False, "headless"), (True, "ask_players"))
SEEDS = 150
crashes = []
totals = collections.Counter()
all_refusals = collections.Counter()
for ask, label in modes:
    for seed in range(SEEDS):
        try:
            plays, answers, refusals, c = one_fight(seed, ask)
            totals["plays"] += plays
            totals["answers"] += answers
            totals["fights"] += 1
            totals["finished"] += c.is_over()
            all_refusals.update(refusals)
        except Exception:
            crashes.append((label, seed, traceback.format_exc()))

print("legal refusals, by message shape:")
# collapse unit ids / numbers so identical rules group together
import re
grouped = collections.Counter()
for msg, n in all_refusals.items():
    key = re.sub(r"\b(p\d|e\d|\d+)\b", "N", msg)
    key = re.sub(r"^[A-Z][A-Za-z' ]+ (cannot|must|has|requires|is|needs)", r"<card> \1", key)
    grouped[key] += n
for key, n in grouped.most_common():
    print("  %5d  %s" % (n, key))
for label, seed, tb in crashes[:3]:
    print()
    print("=== CRASH %s seed %d ===" % (label, seed))
    print(tb)
print()
print("fights          :", totals["fights"], "(%d seeds x 2 modes)" % SEEDS)
print("cards played    :", totals["plays"])
print("choices answered:", totals["answers"])
print("fights finished :", totals["finished"], "(rest hit the turn cap)")
print("crashes         :", len(crashes))

import sys as _sys
_sys.exit(1 if crashes else 0)
