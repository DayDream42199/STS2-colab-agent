# -*- coding: utf-8 -*-
"""No card may permanently mutate the deck it came from."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from game_engine.entities import Player, seed_content
from game_engine.combat import CombatEngine
import game_engine.cards as C
import game_engine.enemies as E

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  [{'ok' if ok else 'FAIL'}] {label}: got {got!r}, want {want!r}")
    if not ok:
        FAILS.append(label)


def fingerprint(card):
    """Every per-instance field a combat effect could plausibly write."""
    return (
        card.name,
        card.cost,
        card.upgraded,
        card.temp_cost,
        card.replay,
        card.bound,
        card.combat_bonus_damage,
        card.exhausts,
        card.ethereal,
        card.retain,
        card.innate,
        tuple(sorted(card.values.items())),
        tuple(sorted(card.upgrade_values.items())),
    )


def bag(hp=100000):
    """A punching bag that cannot die or kill, so the fight runs its course."""
    e = E.make_nibbit()
    e.max_hp = e.hp = hp
    return e


def exercise(factory, seed=0, turns=6, allies=0):
    """Put 3 copies of a card in a deck, fight, end, start again."""
    deck = [factory() for _ in range(3)] + C.make_starter_deck()
    p = Player("P", 400, 99, deck=deck)
    party = [p] + [Player("Ally%d" % i, 400, 99, deck=C.make_starter_deck())
                   for i in range(allies)]
    before = [fingerprint(c) for c in p.deck_template]

    enemy = bag()
    eng = CombatEngine(party, [enemy], seed=seed, scale_enemies=False)
    eng.start_player_turn()

    name = factory().name
    plays = 0
    for _ in range(turns):
        if eng.is_over:
            break
        for _ in range(30):
            playable = eng.playable_cards(p)
            if not playable:
                break
            card = playable[0]
            was = card.name
            if not eng.play_card(p, card, target=enemy):
                break
            if was == name:
                plays += 1
        if eng.is_over:
            break
        eng.end_player_turn()
        if not eng.is_over:
            eng.run_enemy_turn()
        if not eng.is_over:
            eng.start_player_turn()

    enemy.hp = 0
    enemy.alive = False
    eng._check_victory_defeat()

    eng2 = CombatEngine(party, [bag()], seed=seed + 1, scale_enemies=False)
    eng2.start_player_turn()

    after = [fingerprint(c) for c in p.deck_template]
    return before, after, plays


POOLS = [
    ("Ironclad pool", C.CARD_POOL_IRONCLAD),
    ("Ironclad Ancient", C.ANCIENT_CARDS_IRONCLAD),
    ("Colorless pool", C.COLORLESS_POOL),
    ("Colorless Ancient", C.ANCIENT_COLORLESS),
    ("Curses", C.CURSE_POOL),
    ("Status cards", C.STATUS_CARDS),
]

print("Playing every card through a full combat, then checking its deck")
print()

total = 0
never_played = []
errors = []
mutated = []

for label, pool in POOLS:
    dirty = 0
    unplayed = 0
    for factory in pool:
        total += 1
        allies = 1 if factory().target == C.TargetMode.ALLY else 0
        try:
            before, after, plays = exercise(factory, allies=allies)
        except Exception as exc:
            errors.append((factory().name, repr(exc)))
            continue
        if len(before) != len(after):
            mutated.append((factory().name, "deck LENGTH changed"))
            dirty += 1
            continue
        if before != after:
            diff = next((b, a) for b, a in zip(before, after) if b != a)
            mutated.append((factory().name, "{} -> {}".format(diff[0], diff[1])))
            dirty += 1
        if plays == 0:
            unplayed += 1
            never_played.append(factory().name)
    print("  {:<20} {:>3} cards   {:>2} mutated   {:>2} never resolved".format(
        label, len(pool), dirty, unplayed))

print()
print("one-off makers (Status cards enemies hand out, Primal Force's token)")
ONE_OFFS = [C.make_wound, C.make_infection, C.make_dazed, C.make_slimed,
            C.make_beckon, C.make_toxic, C.make_burn, C.make_frantic_escape,
            C.make_giant_rock, C.make_wither]
for mk in ONE_OFFS:
    total += 1
    try:
        before, after, _ = exercise(mk)
        if before != after:
            mutated.append((mk().name, "one-off mutated its deck"))
    except Exception as exc:
        errors.append((mk().name, repr(exc)))
print("  {} one-off cards checked".format(len(ONE_OFFS)))

print()
check("cards swept", total > 200, True)
check("cards that permanently mutated deck_template", mutated, [])
check("cards that raised", errors, [])

unplayable_names = {c.name for c in
                    [f() for f in C.CURSE_POOL] + [mk() for mk in C.STATUS_CARDS]
                    if c.is_unplayable()}
silent = [n for n in never_played if n not in unplayable_names]
print()
print("  {} card(s) never resolved; {} of those are playable".format(
    len(never_played), len(silent)))
if silent:
    print("  (unexercised, so unproven here: {})".format(
        ", ".join(sorted(silent)[:12]) + ("..." if len(silent) > 12 else "")))

print()
print("The helpers still revert, positively (not just 'nothing broke')")
seed_content(0)
deck = C.make_starter_deck()
p = Player("P", 80, 3, deck=deck)
eng = CombatEngine([p], [bag()], seed=0, scale_enemies=False)
eng.start_player_turn()
card = p.hand[0]
p.upgrade_for_combat(card)
p.set_temp_cost(card, 0, scope="combat")
p.grant_replay(card)
check("upgrade_for_combat takes effect during the fight", card.upgraded, True)
check("set_temp_cost takes effect", card.temp_cost, 0)
check("grant_replay takes effect", card.replay, 1)
eng2 = CombatEngine([p], [bag()], seed=1, scale_enemies=False)
check("...upgrade reverted next combat", card.upgraded, False)
check("...temp cost reverted", card.temp_cost, None)
check("...replay reverted", card.replay, 0)

print()
if FAILS:
    print(f"FAILURE: {len(FAILS)} check(s) failed")
    for f in FAILS:
        print("  - " + f)
    for name, why in mutated[:15]:
        print("    MUTATED {}: {}".format(name, why))
    for name, why in errors[:15]:
        print("    RAISED  {}: {}".format(name, why))
    sys.exit(1)
print("all deck-purity checks passed")
