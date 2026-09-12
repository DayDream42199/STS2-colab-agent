# -*- coding: utf-8 -*-
"""Play every card in the registry upgraded, and check nothing breaks."""
import random, sys, traceback
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))
from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Registry.card_registry import create_card, known_card_ids
from GameEngine.Cards._card_ref import CardRef
from GameEngine.Cards._card_enums import TargetType

broke, unplayable, changed, refused = [], 0, 0, 0
for cid in known_card_ids():
    for upgraded, rep in ((False, 0), (True, 0), (False, 2)):
        ally = create_ally("testally1", "p1", rng=random.Random(4))
        mate = create_ally("testally1", "p2", rng=random.Random(4))
        enemies = [create_enemy("dummy1", "e%d" % i, rng=random.Random(4))
                   for i in (1, 2)]
        c = Combat([ally, mate], enemies, rng=random.Random(4))
        c.start()
        for e in enemies:
            e.current_hp = e.max_hp = 900
        ally.energy = 9
        ref = CardRef(cid, upgraded=upgraded, replay=rep)
        ally.hand = [ref] + [CardRef("strike"), CardRef("defend")]
        ally.draw_pile = [CardRef("strike")] * 8
        ally.discard_pile = [CardRef("defend")] * 3
        card = create_card(ref)
        if not card.properties.playable:
            unplayable += 1
            continue
        ally.energy = 99          # Midnight's cost climbs past a normal bar
        aim = {TargetType.ALLY: mate, TargetType.SELF: ally}.get(
            card.target_type, enemies[0])
        try:
            c.play_card(ally, 0, target=aim)
        except ValueError as error:
            # The hand forbade it (Clash, Enthralled). A refusal is the card
            # working, not the card breaking.
            if "out of this hand" in str(error) or "must be played first" in str(error):
                refused += 1
            else:
                broke.append((cid, upgraded, rep, "ValueError: %s" % error))
        except Exception:
            broke.append((cid, upgraded, rep, traceback.format_exc().strip().splitlines()[-1]))

    # did the upgrade actually change anything the card reads?
    plain, up = create_card(cid), create_card(CardRef(cid, upgraded=True))
    fields = [k for k in vars(plain) if k not in ("ref", "upgraded", "properties")]
    if (any(getattr(plain, k) != getattr(up, k) for k in fields)
            or vars(plain.properties) != vars(up.properties)
            or type(plain).UPGRADE is not None
            or [k for k in dir(type(plain)) if k.isupper()
                and getattr(plain, k, None) != getattr(up, k, None)]):
        changed += 1

print("cards swept          :", len(known_card_ids()))
print("upgrade changes a value:", changed)
print("refused by the hand  :", refused)
print("raised while playing :", len(broke))
for row in broke:
    print("   ", row)

import sys as _sys
_sys.exit(1 if broke else 0)
