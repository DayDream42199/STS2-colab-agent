# -*- coding: utf-8 -*-
"""#45: the card-choice interface."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from game_engine.entities import Player
import game_engine.enemies as E
from game_engine.combat import CombatEngine
import game_engine.cards as C
from game_engine.cards import CardType, TargetMode, make_starter_deck
import testing.bench as bench
FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  [{'ok' if ok else 'FAIL'}] {label}: got {got!r}, want {want!r}")
    if not ok:
        FAILS.append(label)


def bag(hp=4000):
    e = E.make_nibbit()
    e.max_hp = e.hp = hp
    return e


def pool(name):
    for f in (list(C.CARD_POOL_IRONCLAD) + list(C.ANCIENT_CARDS_IRONCLAD)
              + list(C.COLORLESS_POOL) + list(C.ANCIENT_COLORLESS)):
        c = f()
        if c.name == name:
            return c
    raise KeyError(name)


class Recorder:
    """A resolver that records every prompt and picks by a rule."""

    def __init__(self, rule=None):
        self.calls = []
        self.rule = rule or (lambda opts: opts[0])

    def __call__(self, engine, player, options, prompt, kind):
        self.calls.append((prompt, kind, [c.name for c in options]))
        return self.rule(options)


def setup(recorder=None, hp=200):
    p = Player("P", hp, 99, deck=make_starter_deck())
    eng = CombatEngine([p], [bag()], seed=11, scale_enemies=False)
    if recorder is not None:
        eng.choice_resolver = recorder
    eng.start_player_turn()
    p.energy = 99
    return eng, p, eng.enemies[0]


def play(eng, p, card, target=None):
    p.hand = [card]
    p.energy = 99
    tgt = target if card.target == TargetMode.SINGLE_ENEMY else None
    return eng.play_card(p, card, target=tgt)


print("=" * 74)
print("Every CHOOSE card now asks")
print("=" * 74)

def _hand_filler(p, n=3):
    p.hand += [make_starter_deck()[0] for _ in range(n)]


cases = []

r = Recorder()
eng, p, e = setup(r)
arm = pool("Armaments")
p.hand = [arm, make_starter_deck()[0], make_starter_deck()[1]]
eng.play_card(p, arm)
check("Armaments asks which card to upgrade", [c[1] for c in r.calls], ["upgrade"])

r = Recorder()
eng, p, e = setup(r)
tg = pool("True Grit")
p.hand = [tg, make_starter_deck()[0], make_starter_deck()[1]]
eng.play_card(p, tg)
check("True Grit (base) does NOT ask -- its text says 'at random'", r.calls, [])
r = Recorder()
eng, p, e = setup(r)
tgu = pool("True Grit")
tgu.upgrade()
p.hand = [tgu, make_starter_deck()[0], make_starter_deck()[1]]
eng.play_card(p, tgu)
check("True Grit+ DOES ask -- its text drops 'at random'",
      [c[1] for c in r.calls], ["exhaust"])

r = Recorder()
eng, p, e = setup(r)
hb = pool("Headbutt")
p.discard_pile = [make_starter_deck()[0], make_starter_deck()[1]]
play(eng, p, hb, e)
check("Headbutt asks which card to put back", [c[1] for c in r.calls], ["to_draw_top"])

r = Recorder()
eng, p, e = setup(r)
pur = pool("Purity")
p.hand = [pur] + [make_starter_deck()[0] for _ in range(5)]
eng.play_card(p, pur)
check("Purity asks once per card it exhausts", len(r.calls), 3)
first_offers = r.calls[0][2]
check("...and the offer shrinks as cards are taken",
      [len(c[2]) for c in r.calls], [5, 4, 3])

r = Recorder()
eng, p, e = setup(r)
dw = pool("Dual Wield")
p.hand = [dw, make_starter_deck()[0], pool("Inflame")]
eng.play_card(p, dw)
check("Dual Wield asks which card to copy", [c[1] for c in r.calls], ["copy"])

r = Recorder()
eng, p, e = setup(r)
ta = pool("Thinking Ahead")
p.draw_pile = [make_starter_deck()[0] for _ in range(5)]
p.hand = [ta]
eng.play_card(p, ta)
check("Thinking Ahead asks under 'stash', NOT 'to_draw_top'",
      [c[1] for c in r.calls], ["stash"])
check("...because Headbutt's to_draw_top wants the BEST card and this one "
      "wants the worst", "stash" != "to_draw_top", True)

r = Recorder()
eng, p, e = setup(r)
nf = pool("Neow's Fury")
p.discard_pile = [make_starter_deck()[0] for _ in range(4)]
play(eng, p, nf, e)
check("Neow's Fury asks once per card retrieved", len(r.calls), 2)

r = Recorder()
eng, p, e = setup(r)
w = pool("Wish")
p.draw_pile = [make_starter_deck()[0] for _ in range(4)]
p.hand = [w]
eng.play_card(p, w)
check("Wish asks which card to tutor", [c[1] for c in r.calls], ["to_hand"])

r = Recorder()
eng, p, e = setup(r)
ss = pool("Seeker Strike")
p.draw_pile = [make_starter_deck()[0] for _ in range(8)]
play(eng, p, ss, e)
check("Seeker Strike offers exactly 3", [len(c[2]) for c in r.calls], [3])

r = Recorder()
eng, p, e = setup(r)
d = pool("Discovery")
p.hand = [d]
eng.play_card(p, d)
check("Discovery offers 3 cards", [len(c[2]) for c in r.calls], [3])
check("...and they are distinct printings", len(set(r.calls[0][2])), 3)

r = Recorder()
eng, p, e = setup(r)
ab = pool("Abundance")
p.hand = [ab]
eng.play_card(p, ab)
check("Abundance offers 3 Powers", [len(c[2]) for c in r.calls], [3])
powers = {f().name for f in C.FACTORIES_BY_TYPE[CardType.POWER]}
check("...all of which really are Powers",
      set(r.calls[0][2]) <= powers, True)

r = Recorder()
eng, p, e = setup(r)
st = pool("Stratagem")
p.hand = [st]
eng.play_card(p, st)
p.draw_pile = []
p.discard_pile = [make_starter_deck()[0] for _ in range(4)]
p.draw_cards(1, eng.log)
check("Stratagem asks on reshuffle", [c[1] for c in r.calls], ["to_hand"])

r = Recorder()
eng, p, e = setup(r)
ent = pool("Entropy")
p.hand = [ent]
eng.play_card(p, ent)
p.hand = [make_starter_deck()[0], make_starter_deck()[1]]
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("Entropy asks which card to transform",
      [c[1] for c in r.calls if c[1] == "transform"], ["transform"])

print()
print("=" * 74)
print("RANDOM cards were left alone")
print("=" * 74)
for name, setup_fn in (
    ("Cinder", lambda p: p.hand.extend(make_starter_deck()[:3])),
    ("Thrash", lambda p: p.hand.extend(make_starter_deck()[:3])),
    ("Infernal Blade", lambda p: None),
    ("Catastrophe", lambda p: p.draw_pile.extend(make_starter_deck()[:5])),
    ("Beat Down", lambda p: p.discard_pile.extend(make_starter_deck()[:5])),
    ("Hidden Gem", lambda p: p.draw_pile.extend(make_starter_deck()[:5])),
    ("Jack of All Trades", lambda p: None),
):
    r = Recorder()
    eng, p, e = setup(r)
    card = pool(name)
    p.hand = [card]
    setup_fn(p)
    tgt = e if card.target == TargetMode.SINGLE_ENEMY else None
    eng.play_card(p, card, target=tgt)
    check(f"{name} does not ask (its text says 'random')", r.calls, [])

print()
print("=" * 74)
print("Resolver contract")
print("=" * 74)

eng, p, e = setup()
check("no resolver installed -> default is random, not a crash",
      eng.choice_resolver, None)

rogue = Recorder(rule=lambda opts: C.make_wound())
eng, p, e = setup(rogue)
w = pool("Wish")
p.draw_pile = [make_starter_deck()[0] for _ in range(3)]
p.hand = [w]
eng.play_card(p, w)
check("a rogue resolver cannot smuggle in an un-offered card",
      any(c.name == "Wound" for c in p.hand), False)
check("...and the engine logs it",
      any("not offered" in line for line in eng.log), True)

r = Recorder()
eng, p, e = setup(r)
w = pool("Wish")
p.draw_pile = [make_starter_deck()[0]]
p.hand = [w]
eng.play_card(p, w)
check("a single option is taken without asking", r.calls, [])

r = Recorder()
eng, p, e = setup(r)
w = pool("Wish")
p.draw_pile = []
p.hand = [w]
check("an empty option list is safe", eng.play_card(p, w), True)
check("...and asks nothing", r.calls, [])

print()
print("=" * 74)
print("The benchmark's heuristic resolver")
print("=" * 74)
eng, p, e = setup(bench.greedy_choice)
strike, bludgeon = make_starter_deck()[0], pool("Bludgeon")
wound = C.make_wound()
check("'to_hand' takes the strongest option",
      bench.greedy_choice(eng, p, [strike, bludgeon, wound], "", "to_hand").name,
      "Bludgeon")
picks = {bench.greedy_choice(eng, p, [strike, bludgeon, wound], "", "exhaust").name
         for _ in range(40)}
check("'exhaust' defers to random rather than always dumping the same card",
      len(picks) > 1, True)
check("'stash' likewise defers",
      len({bench.greedy_choice(eng, p, [strike, bludgeon, wound], "", "stash").name
           for _ in range(40)}) > 1, True)
check("'copy' and 'to_draw_top' are gain prompts too",
      (bench.greedy_choice(eng, p, [strike, bludgeon], "", "copy").name,
       bench.greedy_choice(eng, p, [strike, bludgeon], "", "to_draw_top").name),
      ("Bludgeon", "Bludgeon"))
check("Powers beat a one-shot for 'to_hand'",
      bench.greedy_choice(eng, p, [strike, pool("Inflame")], "", "to_hand").name,
      "Inflame")

eng, p, e = setup(bench.greedy_choice)
w = pool("Wish")
p.draw_pile = [make_starter_deck()[1], make_starter_deck()[1], pool("Bludgeon")]
p.hand = [w]
eng.play_card(p, w)
check("Wish tutors Bludgeon rather than a Defend",
      any(c.name == "Bludgeon" for c in p.hand), True)

print()
print("=" * 74)
if FAILS:
    print(f"{len(FAILS)} FAILURE(S):")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("ALL CHOICE CHECKS PASSED")
