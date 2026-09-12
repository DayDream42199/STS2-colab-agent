"""Batch 9: the 21 cards that needed no new system."""
import random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Registry.card_registry import create_card, known_card_ids
from GameEngine.Effects.InstantEffects.instant_damage import InstantDamage
from GameEngine.Effects.StatusEffects.strength import Strength
from GameEngine.Events.game_event import GameEvent

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

def never_block(enemies):
    """dummy1's second intent is "gain 2 Block", which would silently eat part
    of anything measured across a turn boundary. Pin every enemy to the attack
    intent so damage numbers are readable."""
    for e in enemies:
        e.choose_intent = lambda context=None, e=e: setattr(
            e, "intent", {"type": "attack", "amount": 1})
        e.choose_intent()
        e.block = 0

check("registry has 223 cards", len(known_card_ids()) == 223, len(known_card_ids()))

# --- the plain five --------------------------------------------------------
c, a, es = fight(seed=2)
play(c, a[0], "ultimate_strike", es[0])
check("Ultimate Strike deals 14", es[0].current_hp == 186, es[0].current_hp)

c, a, es = fight(seed=2)
play(c, a[0], "ultimate_defend")
check("Ultimate Defend gains 11 block", a[0].block == 11, a[0].block)

c, a, es = fight(seed=2)
play(c, a[0], "hand_of_greed", es[0])
check("Hand of Greed deals 20", es[0].current_hp == 180, es[0].current_hp)

c, a, es = fight(seed=2)
a[0].energy = 1
play(c, a[0], "production")
check("Production gains 2 energy", a[0].energy == 3, a[0].energy)
check("Production exhausts itself", a[0].exhaust_pile == ["production"],
      a[0].exhaust_pile)

c, a, es = fight(n_enemies=3, seed=2)
play(c, a[0], "dramatic_entrance")
check("Dramatic Entrance hits all 3 for 11",
      [e.current_hp for e in es] == [189] * 3, [e.current_hp for e in es])
check("Dramatic Entrance is innate", create_card("dramatic_entrance").properties.innate)
check("Dramatic Entrance exhausts", a[0].exhaust_pile == ["dramatic_entrance"])

# --- debuffs ---------------------------------------------------------------
c, a, es = fight(n_enemies=2, seed=3)
play(c, a[0], "shockwave")
check("Shockwave applies Weak 3 to all",
      all(e.get_status("weak").amount == 3 for e in es))
check("Shockwave applies Vulnerable 3 to all",
      all(e.get_status("vulnerable").amount == 3 for e in es))
check("Shockwave gives each enemy its own status objects",
      es[0].get_status("weak") is not es[1].get_status("weak"))

c, a, es = fight(seed=3)
es[0].apply_status(Strength(source=es[0], target=es[0], amount=5))
play(c, a[0], "dark_shackles", es[0])
check("Dark Shackles applies 9 Strength loss",
      es[0].get_status("strength_loss_this_turn").amount == 9)
before = a[0].current_hp
a[0].block = 0
c._resolve(InstantDamage(source=es[0], target=a[0], amount=10))
check("Dark Shackles nets the enemy to 6 damage (10 +5 -9)",
      a[0].current_hp == before - 6, before - a[0].current_hp)

# --- party -----------------------------------------------------------------
c, a, es = fight(n_allies=3, seed=4)
a[2].current_hp = 0
play(c, a[0], "rally")
check("Rally blocks every living ally including the caster",
      [x.block for x in a] == [12, 12, 0], [x.block for x in a])

c, a, es = fight(n_allies=3, seed=4)
play(c, a[0], "beacon_of_hope")
play(c, a[0], "ultimate_defend")
check("Beacon of Hope: caster keeps the full 11", a[0].block == 11, a[0].block)
check("Beacon of Hope: others get half, floored",
      [a[1].block, a[2].block] == [5, 5], [a[1].block, a[2].block])
play(c, a[1], "ultimate_defend")
check("Beacon of Hope only reacts to its owner's block",
      [a[0].block, a[1].block, a[2].block] == [11, 16, 5],
      [a[0].block, a[1].block, a[2].block])

# --- armour ----------------------------------------------------------------
c, a, es = fight(seed=5)
never_block(es)
play(c, a[0], "stone_armor")
check("Stone Armor grants no block immediately", a[0].block == 0, a[0].block)
hp = a[0].current_hp
c.end_player_turn()
check("Plating's 4 block is up before the enemy phase, and soaks the hit",
      a[0].current_hp == hp, "hp %d -> %d" % (hp, a[0].current_hp))
check("Plating decays to 3 after paying out",
      a[0].get_status("plating").amount == 3, a[0].get_status("plating").amount)

c2, a2, es2 = fight(seed=5)
play(c2, a2[0], "stone_armor")
a2[0].block = 0
c2._emit(GameEvent.TURN_END, a2[0])
check("Plating pays out exactly 4 block", a2[0].block == 4, a2[0].block)

c, a, es = fight(seed=5)
play(c, a[0], "stone_armor")
play(c, a[0], "eternal_armor")
check("Stone Armor and Eternal Armor stack to 13",
      a[0].get_status("plating").amount == 13, a[0].get_status("plating").amount)

# --- block tricks ----------------------------------------------------------
c, a, es = fight(seed=6)
a[0].block = 17
play(c, a[0], "prolong")
check("Prolong snapshots the current block",
      a[0].get_status("stored_block").amount == 17)
c.end_player_turn()
check("Prolong pays the snapshot next turn, after block is cleared",
      a[0].block == 17, a[0].block)
check("Prolong is spent after paying out",
      a[0].get_status("stored_block") is None
      or a[0].get_status("stored_block").amount == 0)
c.end_player_turn()
check("Prolong does not pay a second time", a[0].block == 0, a[0].block)

c, a, es = fight(seed=6)
play(c, a[0], "panic_button")
check("Panic Button gains its own 30 block", a[0].block == 30, a[0].block)
play(c, a[0], "ultimate_defend")
check("Panic Button then locks out further block", a[0].block == 30, a[0].block)
c.end_player_turn()
play(c, a[0], "ultimate_defend")
check("Panic Button still locked next turn", a[0].block == 0, a[0].block)
c.end_player_turn()
play(c, a[0], "ultimate_defend")
check("Panic Button lockout ends after 2 turns", a[0].block == 11, a[0].block)

c, a, es = fight(seed=7)
play(c, a[0], "the_gambit")
check("The Gambit gains 50 block", a[0].block == 50, a[0].block)
c._resolve(InstantDamage(source=es[0], target=a[0], amount=30))
check("The Gambit survives a fully blocked hit", a[0].is_alive(), a[0].current_hp)
c._resolve(InstantDamage(source=es[0], target=a[0], amount=30))
check("The Gambit kills on the first unblocked point",
      not a[0].is_alive(), a[0].current_hp)

c, a, es = fight(seed=7)
play(c, a[0], "fasten")
play(c, a[0], "defend")
check("Fasten adds 4 to a Defend (5 + 4)", a[0].block == 9, a[0].block)
a[0].block = 0
play(c, a[0], "ultimate_defend")
check("Fasten ignores non-Defend block cards", a[0].block == 11, a[0].block)

# --- powers ----------------------------------------------------------------
c, a, es = fight(seed=8)
play(c, a[0], "prowess")
check("Prowess grants 1 Strength", a[0].get_status("strength").amount == 1)
check("Prowess grants 1 Dexterity", a[0].get_status("dexterity").amount == 1)
play(c, a[0], "ultimate_strike", es[0])
check("Dexterity does not touch damage (14 + 1 Strength)",
      es[0].current_hp == 185, es[0].current_hp)
play(c, a[0], "ultimate_defend")
check("Dexterity adds 1 to block gained", a[0].block == 12, a[0].block)

c, a, es = fight(seed=8)
play(c, a[0], "prep_time")
check("Prep Time grants no Vigor on the turn it lands",
      a[0].get_status("vigor") is None)
c.end_player_turn()
check("Prep Time grants 4 Vigor next turn start",
      a[0].get_status("vigor").amount == 4, a[0].get_status("vigor").amount)
a[0].energy = 5
play(c, a[0], "ultimate_strike", es[0])
check("Vigor adds 4 to the next attack", es[0].current_hp == 182, es[0].current_hp)
a[0].energy = 5
play(c, a[0], "ultimate_strike", es[0])
check("Vigor is spent after one attack", es[0].current_hp == 168, es[0].current_hp)

c, a, es = fight(n_enemies=2, seed=9)
never_block(es)
a[0].apply_status(Strength(source=a[0], target=a[0], amount=10))
play(c, a[0], "rolling_boulder")
check("Rolling Boulder does nothing the turn it lands",
      [e.current_hp for e in es] == [200, 200], [e.current_hp for e in es])
c.end_player_turn()
check("Rolling Boulder hits all for 5, ignoring Strength",
      [e.current_hp for e in es] == [195, 195], [e.current_hp for e in es])
c.end_player_turn()
check("Rolling Boulder grows to 10",
      [e.current_hp for e in es] == [185, 185], [e.current_hp for e in es])

c, a, es = fight(n_enemies=2, seed=9)
never_block(es)
play(c, a[0], "the_bomb")
c.end_player_turn()
check("The Bomb is quiet after 1 turn",
      [e.current_hp for e in es] == [200, 200], [e.current_hp for e in es])
c.end_player_turn()
check("The Bomb is quiet after 2 turns",
      [e.current_hp for e in es] == [200, 200], [e.current_hp for e in es])
c.end_player_turn()
check("The Bomb detonates for 40 on all at the end of turn 3",
      [e.current_hp for e in es] == [160, 160], [e.current_hp for e in es])
c.end_player_turn()
check("The Bomb only goes off once",
      [e.current_hp for e in es] == [160, 160], [e.current_hp for e in es])

# --- hand surgery ----------------------------------------------------------
c, a, es = fight(seed=10)
a[0].hand = ["purity", "strike", "defend", "bash", "anger"]
c.play_card(a[0], 0)
check("Purity exhausts 3 of the 4 remaining cards",
      len(a[0].hand) == 1, a[0].hand)
check("Purity is exhausted too, and is not one of the 3",
      "purity" in a[0].exhaust_pile and len(a[0].exhaust_pile) == 4,
      a[0].exhaust_pile)

c, a, es = fight(seed=10)
a[0].hand = ["purity", "strike"]
c.play_card(a[0], 0)
check("Purity copes with fewer than 3 cards in hand",
      a[0].hand == [] and len(a[0].exhaust_pile) == 2, a[0].exhaust_pile)

c, a, es = fight(seed=11)
a[0].hand = ["primal_force", "strike", "strike", "defend", "bash"]
c.play_card(a[0], 0)
check("Primal Force replaces all 3 Attacks with Giant Rock",
      sorted(a[0].hand) == ["defend", "giant_rock", "giant_rock", "giant_rock"],
      a[0].hand)
check("Primal Force does not exhaust what it transforms",
      a[0].exhaust_pile == [], a[0].exhaust_pile)
check("Primal Force itself goes to the discard",
      a[0].discard_pile == ["primal_force"], a[0].discard_pile)

c, a, es = fight(seed=11)
a[0].hand = ["primal_force", "defend"]
c.play_card(a[0], 0)
check("Primal Force with no Attacks in hand is a no-op",
      a[0].hand == ["defend"], a[0].hand)

print()
print("ALL BATCH 9 CHECKS PASSED" if not bad else "FAILURES: %d" % len(bad))
for b in bad:
    print("   ", b)

import sys as _sys
_sys.exit(1 if bad else 0)
