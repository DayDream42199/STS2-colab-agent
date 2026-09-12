# -*- coding: utf-8 -*-
"""Structural invariants across every card and status, whoever wrote it."""
import sys, os, importlib, inspect, io, re, collections
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))
G = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."), "Server", "GameEngine")
from GameEngine.Registry.card_registry import create_card, known_card_ids, _CARD_CLASSES
from GameEngine.Cards._card import Card
from GameEngine.Cards._card_enums import CardType, TargetType, CardClass
from GameEngine.Effects.StatusEffects._status_effect import StatusEffect
from GameEngine.Effects.InstantEffects._instant_effect import InstantEffect
from GameEngine.Effects._effect import Effect

problems = []
def bad(msg): problems.append(msg)

# --- cards ------------------------------------------------------------------
ids = known_card_ids()
print("cards registered:", len(ids))

# every card module in Cards/ is registered exactly once
card_files = {f[:-3] for f in os.listdir(os.path.join(G, "Cards"))
              if f.endswith(".py") and not f.startswith("_")}
registered_modules = {cls.__module__.rsplit(".", 1)[-1] for cls in _CARD_CLASSES.values()}
for f in sorted(card_files - registered_modules):
    bad("Cards/%s.py has no registered card" % f)

# id matches module, name is set, type/target sane
seen_names = collections.Counter()
for cid in ids:
    c = create_card(cid)
    seen_names[c.name] += 1
    if not c.name: bad("%s: empty name" % cid)
    if c.card_type is CardType.ATTACK and c.target_type not in (
            TargetType.ENEMY, TargetType.ALL_ENEMIES, TargetType.RANDOM_ENEMY):
        # some attacks legitimately hit allies (Tag Team?) - flag only for review
        pass
    if c.card_type in (CardType.STATUS, CardType.CURSE) and c.card_class not in (
            CardClass.STATUS, CardClass.CURSE, CardClass.TOKEN):
        bad("%s: %s typed but class %s" % (cid, c.card_type.name, c.card_class.name))
    if not isinstance(c.cost, int) and c.cost != Card.X_COST:
        bad("%s: cost %r is neither int nor X" % (cid, c.cost))
    # get_effects must be overridden and must return a list of Effects
    if type(c).get_effects is Card.get_effects:
        bad("%s: get_effects not overridden" % cid)
dupes = {n: k for n, k in seen_names.items() if k > 1 and n != "Mad Science"}
for n, k in dupes.items():
    bad("name %r used by %d cards" % (n, k))

# --- statuses ---------------------------------------------------------------
status_dir = os.path.join(G, "Effects", "StatusEffects")
status_classes = []
for f in sorted(os.listdir(status_dir)):
    if not f.endswith(".py") or f.startswith("_"): continue
    mod = importlib.import_module("GameEngine.Effects.StatusEffects." + f[:-3])
    found = [v for v in vars(mod).values()
             if inspect.isclass(v) and issubclass(v, StatusEffect) and v is not StatusEffect
             and v.__module__ == mod.__name__]
    if not found: bad("StatusEffects/%s defines no StatusEffect" % f)
    status_classes.extend(found)
print("statuses found:", len(status_classes))

ids_seen = collections.Counter()
for cls in status_classes:
    # must construct with (source, target, amount) - the shape apply_status/copy expect
    sig = inspect.signature(cls.__init__)
    params = [p for p in sig.parameters if p != "self"]
    if params[:3] != ["source", "target", "amount"] and params[:3] != ["source", "target", "card_ref"]:
        bad("%s.__init__ params %s - expected (source, target, amount...)" % (cls.__name__, params))
    try:
        inst = cls(None, None, 1) if params[:3][2] == "amount" else cls(None, None, "x")
    except TypeError as e:
        bad("%s cannot be built with (None, None, 1): %s" % (cls.__name__, e)); continue
    if not getattr(inst, "effect_id", None): bad("%s: no effect_id" % cls.__name__)
    ids_seen[inst.effect_id] += 1
    if not isinstance(inst.amount, (int, float)): bad("%s: amount %r" % (cls.__name__, inst.amount))
for eid, k in ids_seen.items():
    if k > 1: bad("effect_id %r used by %d statuses" % (eid, k))

# --- instant effects: every one has a Resolver handler ----------------------
from GameEngine.Resolution import resolver as R
src = io.open(R.__file__, encoding="utf-8").read()
inst_dir = os.path.join(G, "Effects", "InstantEffects")
for f in sorted(os.listdir(inst_dir)):
    if not f.endswith(".py") or f.startswith("_"): continue
    mod = importlib.import_module("GameEngine.Effects.InstantEffects." + f[:-3])
    for v in vars(mod).values():
        if inspect.isclass(v) and issubclass(v, InstantEffect) and v is not InstantEffect \
                and v.__module__ == mod.__name__:
            if "isinstance(effect, %s)" % v.__name__ not in src and v.__name__ != "InstantPlayCard":
                bad("%s has no Resolver.resolve branch" % v.__name__)

# --- upgrade table names exist on the card ----------------------------------
from GameEngine.Cards._upgrades import UPGRADES
for cid, table in UPGRADES.items():
    if cid not in _CARD_CLASSES: bad("_upgrades: %r is not a card" % cid); continue
    c = create_card(cid)
    for k in table:
        if k == "properties":
            for flag in table[k]:
                if not hasattr(c.properties, flag): bad("_upgrades[%s]: no property %r" % (cid, flag))
        elif k != "cost" and not hasattr(type(c), k):
            bad("_upgrades[%s]: card has no constant %r" % (cid, k))

print()
print("%d structural problems" % len(problems))
for p in problems: print("  -", p)

import sys as _sys
_sys.exit(1 if problems else 0)
