# -*- coding: utf-8 -*-
"""The 11 relics whose exclusion notes had gone stale (#42)."""
import os
import sys

# The modules under test live one directory up. This used to be a hardcoded
# absolute path, which is why the whole suite only ran on one machine from
# one directory -- and why it lived in a temp folder rather than the repo.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from game_engine.entities import Player
import game_engine.enemies as E
from game_engine.combat import CombatEngine
from game_engine.cards import CARD_POOL_IRONCLAD, make_starter_deck, CardType
import game_engine.relics as R
from game_engine.statuses import StatusType

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  [{'ok' if ok else 'FAIL'}] {label}: got {got!r}, want {want!r}")
    if not ok:
        FAILS.append(label)


def relic(name):
    for r in R.RELIC_POOL_IRONCLAD:
        if r.name == name:
            return r
    raise KeyError(name)


def card(name):
    for f in CARD_POOL_IRONCLAD:
        c = f()
        if c.name == name:
            return c
    for c in make_starter_deck():
        if c.name == name:
            return c
    raise KeyError(name)


def bag(hp=4000):
    e = E.make_nibbit()
    e.max_hp = e.hp = hp
    return e


def setup(relic_names=(), hp=200):
    p = Player("Tester", hp, 99, deck=make_starter_deck())
    for n in relic_names:
        p.add_relic(relic(n))
    eng = CombatEngine([p], [bag()], seed=13, scale_enemies=False)
    eng.start_player_turn()
    p.energy = 99
    return eng, p, eng.enemies[0]


print("=" * 74)
print("Per-card damage relics (apply to EVERY hit, not just the first)")
print("=" * 74)
eng, p, e = setup(["Strike Dummy"])
s = card("Strike")
p.hand = [s]
hp0 = e.hp
eng.play_card(p, s, target=e)
check("Strike Dummy: Strike 6 + 3", hp0 - e.hp, 9)
tw = card("Twin Strike")
p.hand = [tw]
hp0 = e.hp
eng.play_card(p, tw, target=e)
check("...and both hits of Twin Strike get it (5+3 twice)", hp0 - e.hp, 16)
d = card("Defend")
p.hand = [d]
hp0 = e.hp
eng.play_card(p, d)
check("...but Skills are unaffected", hp0 - e.hp, 0)

eng, p, e = setup(["Miniature Cannon"])
up = card("Strike")
up.upgrade()
p.hand = [up]
hp0 = e.hp
eng.play_card(p, up, target=e)
check("Miniature Cannon: upgraded Strike 9 + 3", hp0 - e.hp, 12)
plain = card("Strike")
p.hand = [plain]
hp0 = e.hp
eng.play_card(p, plain, target=e)
check("...un-upgraded Attacks get nothing", hp0 - e.hp, 6)

print()
print("=" * 74)
print("Conditional and persistent state")
print("=" * 74)
eng, p, e = setup(["Red Skull"], hp=100)
p.hp = 100
check("Red Skull dormant above 50% HP", p.deal_attack_damage(6), 6)
p.hp = 50
check("...+3 Strength at exactly 50%", p.deal_attack_damage(6), 9)
p.hp = 20
check("...and below", p.deal_attack_damage(6), 9)
p.hp = 100
check("...and it switches back off", p.deal_attack_damage(6), 6)

# Inert enemy so the enemy phase can't spend the Block being measured.
p = Player("Tester", 200, 99, deck=make_starter_deck())
p.add_relic(relic("Sturdy Clamp"))
eng = CombatEngine([p], [E.make_battle_friend_v1()], seed=13, scale_enemies=False)
eng.start_player_turn()
p.block = 25
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("Sturdy Clamp keeps up to 10 Block", p.block, 10)
p.block = 4
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("...and less than 10 is kept whole", p.block, 4)

eng, p, e = setup(["Ice Cream"])
p.energy = 7
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("Ice Cream conserves energy between turns", p.energy, 7 + p.max_energy)

print()
print("=" * 74)
print("Relics using machinery built for cards and potions")
print("=" * 74)
eng, p, e = setup(["Paper Phrog"])
e.add_status(StatusType.VULNERABLE, 5)
hp0 = e.hp
s = card("Strike")
p.hand = [s]
eng.play_card(p, s, target=e)
check("Paper Phrog: Vulnerable is 75% not 50% (6 -> 10.5 -> 10)", hp0 - e.hp, 10)

eng, p, e = setup(["Shuriken"])
for _ in range(2):
    c = card("Strike")
    p.hand = [c]
    eng.play_card(p, c, target=e)
check("Shuriken: nothing after 2 Attacks", p.get_status(StatusType.STRENGTH), 0)
c = card("Strike")
p.hand = [c]
eng.play_card(p, c, target=e)
check("...+1 Strength on the 3rd", p.get_status(StatusType.STRENGTH), 1)

eng, p, e = setup(["Razor Tooth"])
s = card("Strike")
p.hand = [s]
eng.play_card(p, s, target=e)
check("Razor Tooth upgrades the card it just played", s.upgraded, True)
p.revert_combat_upgrades()
check("...but only for the combat", s.upgraded, False)

eng, p, e = setup(["Mummified Hand"])
p.hand = [card("Bludgeon"), card("Inflame")]
power = card("Inflame")
p.hand = [card("Bludgeon"), power]
eng.play_card(p, power)
free = [c for c in p.hand if c.current_cost(p) == 0]
check("Mummified Hand makes a held card free after a Power", len(free), 1)

eng, p, e = setup(["Unsettling Lamp"])
b = card("Bash")
p.hand = [b]
eng.play_card(p, b, target=e)
check("Unsettling Lamp doubles the first debuff (Bash 2 Vulnerable -> 4)",
      e.get_status(StatusType.VULNERABLE), 4)
b2 = card("Bash")
p.hand = [b2]
eng.play_card(p, b2, target=e)
check("...only once per combat", e.get_status(StatusType.VULNERABLE), 6)

print()
print("=" * 74)
print("Gambling Chip")
print("=" * 74)
p = Player("Tester", 200, 99, deck=make_starter_deck())
p.add_relic(relic("Gambling Chip"))
eng = CombatEngine([p], [bag()], seed=13, scale_enemies=False)
eng.start_player_turn()
check("Gambling Chip redraws a full hand", len(p.hand), 5)
check("...having discarded the first one", len(p.discard_pile), 5)

print()
print("=" * 74)
print("Coverage")
print("=" * 74)
check("relic pool size", len(R.RELIC_POOL_IRONCLAD) + 1, 83)
failed = []
for r in R.RELIC_POOL_IRONCLAD:
    try:
        eng, p, e = setup([r.name])
        eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
    except Exception as ex:
        failed.append((r.name, repr(ex)))
check("every relic survives a full turn cycle", failed, [])

print()
print("=" * 74)
if FAILS:
    print(f"{len(FAILS)} FAILURE(S):")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("ALL RELIC CHECKS PASSED")
