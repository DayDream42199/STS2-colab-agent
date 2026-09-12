"""Batch 10: random card generation, and the free-play tally it needs."""
import random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Registry.card_registry import (create_card, known_card_ids,
                                               generatable_card_ids)
from GameEngine.Cards._card_enums import CardClass, CardType, CardRarity

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))

def fight(n_allies=1, n_enemies=1, seed=1, enemy_hp=200):
    allies = [create_ally("testally1", "p%d" % (i+1), rng=random.Random(seed))
              for i in range(n_allies)]
    enemies = [create_enemy("dummy1", "e%d" % (i+1), rng=random.Random(seed))
               for i in range(n_enemies)]
    c = Combat(allies, enemies, rng=random.Random(seed)); c.start()
    for e in enemies:
        e.current_hp = e.max_hp = enemy_hp
    for a in allies:
        a.energy = 5
    return c, allies, enemies

def play(c, ally, card_id, target=None):
    ally.hand = [card_id]
    return c.play_card(ally, 0, target=target)

check("registry has 223 cards", len(known_card_ids()) == 223, len(known_card_ids()))

# --- what the pool is allowed to contain -----------------------------------
pool = generatable_card_ids()
cards = [create_card(cid) for cid in pool]
check("pool is non-empty", len(pool) > 100, len(pool))
check("no starters in the pool",
      not {"strike", "defend", "bash"} & set(pool))
check("no BASIC rarity", not any(c.rarity is CardRarity.BASIC for c in cards))
check("no ANCIENT rarity", not any(c.rarity is CardRarity.ANCIENT for c in cards),
      [c.name for c in cards if c.rarity is CardRarity.ANCIENT])
check("no curses, statuses or tokens",
      not any(c.card_class in (CardClass.CURSE, CardClass.STATUS, CardClass.TOKEN)
              for c in cards),
      [c.name for c in cards
       if c.card_class in (CardClass.CURSE, CardClass.STATUS, CardClass.TOKEN)])
check("burn/wound/giant_rock excluded",
      not {"burn", "wound", "giant_rock", "dazed", "slimed"} & set(pool))

check("ironclad + colorless partition the pool",
      len(generatable_card_ids(card_class=CardClass.IRONCLAD))
      + len(generatable_card_ids(card_class=CardClass.COLORLESS)) == len(pool))
check("card_type filter returns only that type",
      all(create_card(cid).card_type is CardType.ATTACK
          for cid in generatable_card_ids(card_type=CardType.ATTACK)))
check("rarity filter returns only that rarity",
      all(create_card(cid).rarity is CardRarity.COMMON
          for cid in generatable_card_ids(rarity=CardRarity.COMMON)))
check("filters combine",
      all(create_card(cid).card_class is CardClass.IRONCLAD
          and create_card(cid).card_type is CardType.SKILL
          for cid in generatable_card_ids(card_class=CardClass.IRONCLAD,
                                          card_type=CardType.SKILL)))
check("repeat queries are cached, not rebuilt",
      generatable_card_ids(card_type=CardType.ATTACK)
      is generatable_card_ids(card_type=CardType.ATTACK))

# --- plain generation ------------------------------------------------------
c, a, es = fight(seed=2)
play(c, a[0], "jack_of_all_trades")
check("Jack of All Trades adds 1 card to hand", len(a[0].hand) == 1, a[0].hand)
check("Jack of All Trades adds a Colorless card",
      create_card(a[0].hand[0]).card_class is CardClass.COLORLESS,
      a[0].hand)
check("Jack of All Trades exhausts itself",
      a[0].exhaust_pile == ["jack_of_all_trades"], a[0].exhaust_pile)

c, a, es = fight(seed=3)
a[0].hand = ["stoke", "strike", "defend", "anger"]
c.play_card(a[0], 0)
check("Stoke exhausts the rest of the hand",
      sorted(a[0].exhaust_pile) == ["anger", "defend", "strike"], a[0].exhaust_pile)
check("Stoke refills 1 for 1", len(a[0].hand) == 3, a[0].hand)
check("Stoke's replacements are all Ironclad",
      all(create_card(cid).card_class is CardClass.IRONCLAD for cid in a[0].hand),
      [create_card(cid).name for cid in a[0].hand])
check("Stoke itself is not exhausted (it has no exhaust flag)",
      a[0].discard_pile == ["stoke"], a[0].discard_pile)

c, a, es = fight(seed=3)
a[0].hand = ["stoke"]
c.play_card(a[0], 0)
check("Stoke with an otherwise empty hand is a no-op",
      a[0].hand == [] and a[0].exhaust_pile == [], (a[0].hand, a[0].exhaust_pile))

# --- powers ----------------------------------------------------------------
c, a, es = fight(seed=4)
play(c, a[0], "calamity")
check("Calamity adds nothing when it lands", a[0].hand == [], a[0].hand)
play(c, a[0], "strike", es[0])
check("Calamity adds a card when an Attack is played", len(a[0].hand) == 1, a[0].hand)
check("Calamity's card is an Attack",
      create_card(a[0].hand[0]).card_type is CardType.ATTACK, a[0].hand)
a[0].hand = []
play(c, a[0], "defend")
check("Calamity ignores Skills", a[0].hand == [], a[0].hand)

c, a, es = fight(seed=5)
play(c, a[0], "hello_world")
check("Hello World adds nothing on the turn it lands", a[0].hand == [], a[0].hand)
c.end_player_turn()
drawn = [cid for cid in a[0].hand]
check("Hello World adds a card at turn start", len(drawn) == Combat.HAND_SIZE + 1,
      len(drawn))
commons = generatable_card_ids(card_class=CardClass.IRONCLAD,
                               rarity=CardRarity.COMMON)
check("Hello World's card is a Common", any(cid in commons for cid in drawn))

c, a, es = fight(seed=6)
play(c, a[0], "entropy")
a[0].hand = ["wound"]
c.end_player_turn()
check("Entropy removed the old card from hand", "wound" not in a[0].hand, a[0].hand)
check("Entropy did not exhaust it", a[0].exhaust_pile == [], a[0].exhaust_pile)
check("Entropy put a generatable card in its place",
      any(cid in generatable_card_ids(card_class=CardClass.IRONCLAD)
          for cid in a[0].hand), a[0].hand)

# --- free plays ------------------------------------------------------------
c, a, es = fight(seed=7)
play(c, a[0], "infernal_blade")
check("Infernal Blade adds one Attack", len(a[0].hand) == 1, a[0].hand)
added = a[0].hand[0]
check("Infernal Blade's card is an Attack",
      create_card(added).card_type is CardType.ATTACK, added)
check("Infernal Blade marks it free this turn",
      a[0].free_this_turn == [added], a[0].free_this_turn)
printed = create_card(added).cost
a[0].energy = 0
c.play_card(a[0], 0, target=es[0] if create_card(added).target_type.name == "ENEMY" else None)
check("the free card plays at 0 energy (printed cost %s)" % printed,
      a[0].energy == 0, a[0].energy)
check("the free grant is spent after one play",
      a[0].free_this_turn == [], a[0].free_this_turn)

c, a, es = fight(seed=8)
play(c, a[0], "infernal_blade")
added = a[0].hand[0]
c.end_player_turn()
check("free-this-turn expires at turn start", a[0].free_this_turn == [],
      a[0].free_this_turn)

c, a, es = fight(seed=9)
play(c, a[0], "distraction")
check("Distraction adds one Skill",
      len(a[0].hand) == 1 and create_card(a[0].hand[0]).card_type is CardType.SKILL,
      a[0].hand)
check("Distraction marks it free", len(a[0].free_this_turn) == 1)

c, a, es = fight(seed=10)
play(c, a[0], "jackpot", es[0])
check("Jackpot deals 25", es[0].current_hp == 175, es[0].current_hp)
check("Jackpot adds 3 cards", len(a[0].hand) == 3, a[0].hand)
check("Jackpot marks all 3 free",
      sorted(a[0].free_this_turn) == sorted(a[0].hand),
      (a[0].free_this_turn, a[0].hand))

c, a, es = fight(seed=11)
before = len(a[0].draw_pile)
a[0].hand = ["headbutt", "metamorphosis"]
a[0].discard_pile = ["anger"]
c.play_card(a[0], 0, target=es[0])          # Headbutt: anger to the top
check("Headbutt put a card on top of the draw pile",
      a[0].draw_pile[-1] == "anger", a[0].draw_pile[-1])
was = list(a[0].draw_pile)
c.play_card(a[0], 0)                        # Metamorphosis
check("Metamorphosis adds 3 to the draw pile",
      len(a[0].draw_pile) == before + 4, len(a[0].draw_pile))
# A full reshuffle would scramble these; random insertion cannot. Walk the old
# pile through the new one and check every card is still in the same order.
it = iter(a[0].draw_pile)
check("Metamorphosis inserts without reordering what was already there",
      all(cid in it for cid in was), (was, a[0].draw_pile))
check("Metamorphosis marks 3 free for the combat",
      len(a[0].free_this_combat) == 3, a[0].free_this_combat)
check("Metamorphosis adds Attacks",
      all(create_card(cid).card_type is CardType.ATTACK
          for cid in a[0].free_this_combat))
c.end_player_turn()
check("free-this-combat survives a turn boundary",
      len(a[0].free_this_combat) == 3, a[0].free_this_combat)

# --- the free tally must not leak ------------------------------------------
c, a, es = fight(seed=12)
a[0].free_this_turn = ["bludgeon"]
a[0].hand = ["bludgeon"]
a[0].energy = 0
try:
    c.play_card(a[0], 0, target=None)   # Bludgeon needs a target
    check("a rejected play does not burn the free grant", False, "no raise")
except ValueError:
    check("a rejected play does not burn the free grant",
          a[0].free_this_turn == ["bludgeon"], a[0].free_this_turn)

c, a, es = fight(seed=13)
a[0].free_this_turn = ["strike"]
a[0].hand = ["strike", "strike"]
a[0].energy = 1
c.play_card(a[0], 0, target=es[0])
c.play_card(a[0], 0, target=es[0])
check("only one of two identical cards is free",
      a[0].energy == 0, a[0].energy)

# A free X-cost card spends nothing, so X is 0 and it does nothing. Reachable
# now that Infernal Blade can hand you a Whirlwind.
c, a, es = fight(seed=14)
a[0].free_this_turn = ["whirlwind"]
a[0].hand = ["whirlwind"]
a[0].energy = 3
c.play_card(a[0], 0)
check("a free X-cost card keeps the energy and deals nothing",
      a[0].energy == 3 and es[0].current_hp == es[0].max_hp,
      (a[0].energy, es[0].current_hp))

print()
print("ALL BATCH 10 CHECKS PASSED" if not bad else "FAILURES: %d" % len(bad))
for b in bad:
    print("   ", b)

import sys as _sys
_sys.exit(1 if bad else 0)
