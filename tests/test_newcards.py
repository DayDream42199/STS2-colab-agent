# -*- coding: utf-8 -*-
"""Verification for the 21 newly-ported Ironclad cards and the engine
features they needed."""
import os
import sys

# The modules under test live one directory up. This used to be a hardcoded
# absolute path, which is why the whole suite only ran on one machine from
# one directory -- and why it lived in a temp folder rather than the repo.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from entities import Player
from enemies import make_nibbit
from combat import CombatEngine
from cards import (CARD_POOL_IRONCLAD, ANCIENT_CARDS_IRONCLAD, make_starter_deck,
                   CardType)
from statuses import StatusType

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  [{'ok' if ok else 'FAIL'}] {label}: got {got!r}, want {want!r}")
    if not ok:
        FAILS.append(label)


_ALL = list(CARD_POOL_IRONCLAD) + list(ANCIENT_CARDS_IRONCLAD)


def card(name, upgraded=False):
    for f in _ALL:
        c = f()
        if c.name == name:
            if upgraded:
                c.upgrade()
            return c
    for c in make_starter_deck():
        if c.name == name:
            if upgraded:
                c.upgrade()
            return c
    raise KeyError(name)


def bag(hp=1000):
    e = make_nibbit()
    e.max_hp = e.hp = hp
    return e


def setup(deck=None, enemy=None, hp=500, enemies=None):
    p = Player("Tester", hp, 99, deck=deck if deck is not None else make_starter_deck())
    es = enemies if enemies is not None else [enemy if enemy is not None else bag()]
    eng = CombatEngine([p], es, seed=3, scale_enemies=False)
    eng.start_player_turn()
    p.energy = 99
    return eng, p, es[0]


def play(eng, p, c, target=None):
    if c not in p.hand:
        p.hand.append(c)
    return eng.play_card(p, c, target=target or (eng.enemies_alive() or [None])[0])


print("=" * 74)
print("Innate keyword")
print("=" * 74)
deck = [card("Aggression", upgraded=True)] + [card("Anger") for _ in range(10)]
eng, p, e = setup(deck=deck)
check("Aggression+ (Innate) is in the opening hand", any(c.name == "Aggression" for c in p.hand), True)
deck = [card("Aggression")] + [card("Anger") for _ in range(30)]
eng, p, e = setup(deck=deck)
check("un-upgraded Aggression is NOT Innate", any(c.name == "Aggression" for c in p.hand), False)
check("opening hand is still 5 cards", len(p.hand), 5)

print()
print("=" * 74)
print("Aggression / combat-scoped upgrades (and the Armaments bug it exposed)")
print("=" * 74)
eng, p, e = setup()
agg = card("Aggression")
play(eng, p, agg)
# Fire the turn_start hook directly with a known discard pile, so the check
# can't be confused by the starter deck's own Attacks being reshuffled in.
marker = card("Anger")
p.discard_pile = [marker]
p.hand = []
p.fire_hook("turn_start", turn_number=2)
check("Aggression pulls the Attack into hand", p.hand == [marker], True)
check("...and upgrades it", marker.upgraded, True)
check("...and leaves the discard pile", marker in p.discard_pile, False)
p.revert_combat_upgrades()
check("...with a combat-scoped upgrade, not a permanent one", marker.upgraded, False)

arm_deck = make_starter_deck()
eng, p, e = setup(deck=arm_deck)
target_card = next(c for c in p.hand if not c.upgraded)
p.upgrade_for_combat(target_card)
check("upgrade_for_combat marks the card upgraded", target_card.upgraded, True)
p.revert_combat_upgrades()
check("...and it reverts at combat end (Armaments no longer permanent)",
      target_card.upgraded, False)

print()
print("=" * 74)
print("Simple ports")
print("=" * 74)
eng, p, e = setup()
hp0 = p.hp
play(eng, p, card("Brand"))
check("Brand costs 1 HP", hp0 - p.hp, 1)
check("Brand grants 1 Strength", p.get_status(StatusType.STRENGTH), 1)
check("Brand exhausts a card", len(p.exhaust_pile) >= 1, True)

eng, p, e = setup()
ehp0 = e.hp
play(eng, p, card("Break"))
check("Break deals 20", ehp0 - e.hp, 20)
check("Break applies 5 Vulnerable", e.get_status(StatusType.VULNERABLE), 5)

eng, p, e = setup()
e.add_status(StatusType.VULNERABLE, 2)
play(eng, p, card("Dominate"))
check("Dominate applies 1 Vulnerable (now 3 total)", e.get_status(StatusType.VULNERABLE), 3)
check("Dominate grants Strength = Vulnerable stacks", p.get_status(StatusType.STRENGTH), 3)

print()
print("=" * 74)
print("Vulnerable damage multipliers (Cruelty / Colossus)")
print("=" * 74)
eng, p, e = setup()
e.add_status(StatusType.VULNERABLE, 5)
ehp0 = e.hp
play(eng, p, card("Strike"))              # 6 dmg * 1.5 vulnerable = 9
check("baseline Strike into Vulnerable", ehp0 - e.hp, 9)
eng, p, e = setup()
e.add_status(StatusType.VULNERABLE, 5)
play(eng, p, card("Cruelty"))             # +25%
ehp0 = e.hp
# ADDITIVE with Vulnerable's own 50%, not multiplied on top of it:
# 6 * (1.5 + 0.25) = 10.5 -> 10. Paper Phrog's wording ("75% more rather
# than 50%") is what settles this.
play(eng, p, card("Strike"))
check("Cruelty adds 25% vs Vulnerable", ehp0 - e.hp, 10)

eng, p, e = setup()
p.add_status(StatusType.VULNERABLE, 0)
e.add_status(StatusType.VULNERABLE, 5)
play(eng, p, card("Colossus"))
check("Colossus grants 4 block", p.block, 4)
p.block = 0
hp0 = p.hp
e.deal_attack_damage(10)
p.take_damage(10, log=eng.log, attacker=e)
check("Colossus halves damage from a Vulnerable attacker", hp0 - p.hp, 5)
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
p.block = 0
hp0 = p.hp
p.take_damage(10, log=eng.log, attacker=e)
check("...and it is gone next turn", hp0 - p.hp, 10)

print()
print("=" * 74)
print("Turn-scoped retaliation and triggers")
print("=" * 74)
eng, p, e = setup()
play(eng, p, card("Flame Barrier"))
check("Flame Barrier grants 12 block", p.block, 12)
check("Flame Barrier grants 4 turn-Thorns", p.get_status(StatusType.THORNS_THIS_TURN), 4)
ehp0 = e.hp
p.take_damage(3, log=eng.log, attacker=e)
check("...which retaliates when attacked", ehp0 - e.hp, 4)
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("...and expires at end of turn", p.get_status(StatusType.THORNS_THIS_TURN), 0)

eng, p, e = setup()
ehp0 = e.hp
play(eng, p, card("Grapple"))             # 7 damage
after_hit = e.hp
check("Grapple deals 7", ehp0 - after_hit, 7)
p.gain_block(5)
check("...then 5 more whenever you gain Block", after_hit - e.hp, 5)

print()
print("=" * 74)
print("Dynamic costs")
print("=" * 74)
eng, p, e = setup()
stomp = card("Stomp")
check("Stomp base cost", stomp.current_cost(p), 3)
play(eng, p, card("Strike"))
check("Stomp after 1 Attack", stomp.current_cost(p), 2)
play(eng, p, card("Strike"))
play(eng, p, card("Strike"))
check("Stomp after 3 Attacks (floored at 0)", stomp.current_cost(p), 0)
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("Stomp resets next turn", stomp.current_cost(p), 3)

eng, p, e = setup()
mid = card("Midnight")
check("Midnight base cost", mid.current_cost(p), 12)
for _ in range(4):
    eng.exhaust_card(p, card("Anger"))
check("Midnight after 4 exhausts", mid.current_cost(p), 8)

eng, p, e = setup()
p.energy = 99
play(eng, p, card("Unrelenting"))
check("Unrelenting arms a free Attack", p.next_attack_free, True)
strike = card("Strike")
check("...so the next Attack costs 0", strike.current_cost(p), 0)
before = p.energy
play(eng, p, strike)
check("...and really is free", p.energy, before)
check("...consumed after one use", p.next_attack_free, False)

eng, p, e = setup()
play(eng, p, card("Corruption"))
skill = card("Shrug It Off")
check("Corruption makes Skills cost 0", skill.current_cost(p), 0)
play(eng, p, skill)
check("...and exhausts them", skill in p.exhaust_pile, True)

print()
print("=" * 74)
print("Cards that play other cards")
print("=" * 74)
eng, p, e = setup()
play(eng, p, card("One-Two Punch"))
ehp0 = e.hp
play(eng, p, card("Strike"))
check("One-Two Punch replays the next Attack (6+6)", ehp0 - e.hp, 12)
ehp0 = e.hp
play(eng, p, card("Strike"))
check("...only once", ehp0 - e.hp, 6)

eng, p, e = setup()
play(eng, p, card("Hellraiser"))
ehp0 = e.hp
p.hand = []
p.draw_pile = []
drawn = card("Strike")
p.draw_pile.append(drawn)
p.draw_cards(1, eng.log)
check("Hellraiser auto-plays a drawn Strike", ehp0 - e.hp, 6)
check("...and that exact card does not stay in hand", drawn in p.hand, False)
check("...it goes to the discard pile", drawn in p.discard_pile, True)
# A non-Strike draw must be left alone.
eng, p, e = setup()
play(eng, p, card("Hellraiser"))
p.hand = []
p.draw_pile = [card("Defend")]
ehp0 = e.hp
p.draw_cards(1, eng.log)
check("a drawn non-Strike is untouched", (len(p.hand), ehp0 - e.hp), (1, 0))

eng, p, e = setup()
play(eng, p, card("Stampede"))
p.hand = [card("Strike")]
ehp0 = e.hp
eng.end_player_turn()
check("Stampede plays a random Attack at end of turn", ehp0 - e.hp, 6)

eng, p, e = setup()
howl = card("Howl from Beyond")
ehp0 = e.hp
play(eng, p, howl)
check("Howl from Beyond deals 18 to all", ehp0 - e.hp, 18)
eng.exhaust_card(p, howl)
ehp0 = e.hp
eng.end_player_turn()
check("...and replays from the exhaust pile at end of turn", ehp0 - e.hp, 18)
check("...staying in the exhaust pile", howl in p.exhaust_pile, True)

print()
print("=" * 74)
print("Hand manipulation")
print("=" * 74)
eng, p, e = setup()
play(eng, p, card("Juggling"))
p.hand = []
for i in range(2):
    play(eng, p, card("Strike"))
    p.hand = [c for c in p.hand if c.name != "Strike"]
check("no copy after 2 Attacks", sum(1 for c in p.hand if c.name == "Strike"), 0)
play(eng, p, card("Uppercut"))     # the third Attack
check("Juggling copies the THIRD Attack into hand",
      sum(1 for c in p.hand if c.name == "Uppercut"), 1)
play(eng, p, card("Strike"))
p.hand = [c for c in p.hand if c.name != "Uppercut"]
check("...and not the fourth", sum(1 for c in p.hand if c.name == "Strike"), 0)

eng, p, e = setup()
p.hand = [card("Strike"), card("Strike"), card("Defend")]
play(eng, p, card("Primal Force"))
check("Primal Force turns 2 Attacks into Giant Rock",
      sum(1 for c in p.hand if c.name == "Giant Rock"), 2)
check("...leaves the Skill alone", sum(1 for c in p.hand if c.name == "Defend"), 1)
rock = next(c for c in p.hand if c.name == "Giant Rock")
ehp0 = e.hp
play(eng, p, rock)
check("Giant Rock deals 20", ehp0 - e.hp, 20)

eng, p, e = setup()
p.hand = [card("Strike"), card("Strike"), card("Defend")]
play(eng, p, card("Stoke"))
check("Stoke exhausts the hand", len(p.exhaust_pile), 3)
check("...and refills it with the same count", len(p.hand), 3)

print()
print("=" * 74)
print("Applier-side events and temporary stat loss")
print("=" * 74)
# Control first: Bash alone draws nothing. play() adds the card to hand and
# then plays it, so hand size is unchanged unless something draws.
eng, p, e = setup()
before = len(p.hand)
play(eng, p, card("Bash"))
check("control: Bash alone draws nothing", len(p.hand), before)
eng, p, e = setup()
play(eng, p, card("Vicious"))
before = len(p.hand)
play(eng, p, card("Bash"))     # applies Vulnerable -> Vicious draws 1
check("Vicious draws when YOU apply Vulnerable", len(p.hand), before + 1)
before = len(p.hand)
play(eng, p, card("Strike"))   # no Vulnerable applied
check("...and not on an unrelated Attack", len(p.hand), before)

eng, p, e = setup()
e.add_status(StatusType.STRENGTH, 12)
play(eng, p, card("Mangle"))
check("Mangle records 10 Strength loss", e.get_status(StatusType.STRENGTH_LOSS_THIS_TURN), 10)
check("Mangle does not touch real Strength", e.get_status(StatusType.STRENGTH), 12)
check("net attack damage reflects the loss", e.deal_attack_damage(5), 7)
e.decay_statuses_end_of_turn()
check("...and it wears off", e.deal_attack_damage(5), 17)

print()
print("=" * 74)
print("Full pool sanity: every card plays without error")
print("=" * 74)
p = Player("Ironclad", 99999, 99, deck=[f() for f in _ALL])
punching = bag(hp=10 ** 7)
eng = CombatEngine([p], [punching], seed=1, scale_enemies=False)
eng.start_player_turn()
p.hand = list(p.draw_pile)
p.draw_pile = []
failed = []
for c in list(p.hand):
    if c not in p.hand or eng.is_over:
        continue
    p.energy = 99
    if not eng.play_card(p, c, target=punching):
        failed.append(c.name)
check("every pool + ancient card plays cleanly", failed, [])
check("pool size (86) + ancient (2) + basic (3) = wiki's 91",
      len(CARD_POOL_IRONCLAD) + len(ANCIENT_CARDS_IRONCLAD) + 3, 91)

print()
print("=" * 74)
if FAILS:
    print(f"{len(FAILS)} FAILURE(S):")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("ALL NEW-CARD CHECKS PASSED")
