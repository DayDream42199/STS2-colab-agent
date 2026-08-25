"""Confirmation tests for suspected bugs found in a full read-through."""
import os
import sys

# The modules under test live one directory up. This used to be a hardcoded
# absolute path, which is why the whole suite only ran on one machine from
# one directory -- and why it lived in a temp folder rather than the repo.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from entities import Player
from enemies import Enemy, make_nibbit, make_axe_raider
from combat import CombatEngine
from cards import CARD_POOL_IRONCLAD, CardType, make_starter_deck
from statuses import StatusType
from relics import RELIC_POOL_IRONCLAD, BURNING_BLOOD

pool = {}
for f in CARD_POOL_IRONCLAD:
    pool[f().name] = f
def fresh(name): return pool[name]()

results = []
def check(label, condition, detail=""):
    results.append((label, condition, detail))
    print(f"{'CONFIRMED BUG' if condition else 'ok (no bug)':<16} {label}")
    if detail:
        print(f"                 {detail}")


# ---- 1. Enemy debuffs never decay -------------------------------------
p = Player('P', max_hp=200, max_energy=99, deck=make_starter_deck())
e = make_nibbit(); e.hp = e.max_hp = 500
eng = CombatEngine([p], [e], seed=1)
eng.start_player_turn()
e.add_status(StatusType.VULNERABLE, 2)
for _ in range(6):
    eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("Enemy Vulnerable never decays (permanent debuff)",
      e.get_status(StatusType.VULNERABLE) == 2,
      f"after 6 full turns, Vulnerable still = {e.get_status(StatusType.VULNERABLE)} (should have expired)")


# ---- 2. Enemy poison never ticks --------------------------------------
p = Player('P', max_hp=200, max_energy=99, deck=make_starter_deck())
e = make_nibbit(); e.hp = e.max_hp = 500
eng = CombatEngine([p], [e], seed=1)
eng.start_player_turn()
e.add_status(StatusType.POISON, 10)
hp_before = e.hp
for _ in range(4):
    eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("Enemy Poison never ticks (0 damage dealt)",
      e.hp == hp_before,
      f"after 4 turns with 10 Poison: hp {hp_before} -> {e.hp}, poison still {e.get_status(StatusType.POISON)}")


# ---- 3. Enemy block never clears --------------------------------------
p = Player('P', max_hp=500, max_energy=99, deck=make_starter_deck())
axe = make_axe_raider(); axe.hp = axe.max_hp = 500
eng = CombatEngine([p], [axe], seed=1)
eng.start_player_turn()
for _ in range(6):
    eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("Enemy Block never clears (accumulates forever)",
      axe.block > 5,
      f"Axe Raider block after 6 turns = {axe.block} (Swing grants 5, should not stack across turns)")


# ---- 4. Enemy Ritual/Metallicize/Regen never tick ---------------------
p = Player('P', max_hp=200, max_energy=99, deck=make_starter_deck())
e = make_nibbit(); e.hp = e.max_hp = 500
eng = CombatEngine([p], [e], seed=1)
eng.start_player_turn()
e.add_status(StatusType.METALLICIZE, 5)
e.add_status(StatusType.RITUAL, 2)
for _ in range(3):
    eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("Enemy Metallicize/Ritual never fire",
      e.block == 0 and e.get_status(StatusType.STRENGTH) == 0,
      f"after 3 turns: block={e.block} (expect >0), strength={e.get_status(StatusType.STRENGTH)} (expect >0)")


# ---- 5. Infernal Blade double-exhaust ---------------------------------
p = Player('P', max_hp=200, max_energy=99, deck=make_starter_deck())
e = make_nibbit(); e.hp = e.max_hp = 500
eng = CombatEngine([p], [e], seed=1)
eng.start_player_turn()
card = fresh('Infernal Blade')
p.hand = [card]
exh_before = eng.total_exhausted_this_combat
eng.play_card(p, card)
occurrences = sum(1 for c in p.exhaust_pile if c is card)
check("Infernal Blade exhausts itself TWICE",
      occurrences == 2 or (eng.total_exhausted_this_combat - exh_before) > 1,
      f"card appears {occurrences}x in exhaust_pile; exhaust counter +{eng.total_exhausted_this_combat - exh_before}")


# ---- 5b. knock-on: Feel No Pain double-triggers on Infernal Blade -----
p = Player('P', max_hp=200, max_energy=99, deck=make_starter_deck())
e = make_nibbit(); e.hp = e.max_hp = 500
eng = CombatEngine([p], [e], seed=1)
eng.start_player_turn()
fnp = fresh('Feel No Pain')
p.hand = [fnp]
eng.play_card(p, fnp)
p.block = 0
blade = fresh('Infernal Blade')
p.hand = [blade]
eng.play_card(p, blade)
check("Feel No Pain double-triggers from Infernal Blade's double exhaust",
      p.block > 3,
      f"block gained = {p.block} (Feel No Pain grants 3 per exhaust; expect 3, not 6)")


# ---- 6. Spite upgraded should hit 3 times -----------------------------
p = Player('P', max_hp=200, max_energy=99, deck=make_starter_deck())
e = make_nibbit(); e.hp = e.max_hp = 500
eng = CombatEngine([p], [e], seed=1)
eng.start_player_turn()
sp = fresh('Spite'); sp.upgrade()
p.lose_hp(1, log=eng.log)
p.hand = [sp]
hp0 = e.hp
eng.play_card(p, sp, target=e)
dealt = hp0 - e.hp
check("Spite+ hits only 2x (card text says 3x)",
      dealt == 10,
      f"upgraded Spite dealt {dealt} (5x2); text says 'hits 3 times' = 15")


# ---- 7. end_player_turn has no _combat_over guard -> double combat-end -
p = Player('P', max_hp=200, max_energy=99, deck=make_starter_deck())
p.add_relic(BURNING_BLOOD)
e = make_nibbit(); e.hp = e.max_hp = 1
eng = CombatEngine([p], [e], seed=1)
eng.start_player_turn()
p.hp = 100
strike = fresh('Bludgeon')
p.hand = [strike]
eng.play_card(p, strike, target=e)
hp_after_first = p.hp
eng.end_player_turn()      # called again after combat already over
hp_after_second = p.hp
victory_lines = sum(1 for l in eng.log if 'VICTORY' in l)
check("end_player_turn() after victory re-fires on_combat_end relics",
      hp_after_second > hp_after_first or victory_lines > 1,
      f"Burning Blood heal applied twice: hp {hp_after_first} -> {hp_after_second}; VICTORY logged {victory_lines}x")


# ---- 8. Drum of Battle re-registers its hook on every play ------------
p = Player('P', max_hp=200, max_energy=99, deck=make_starter_deck())
e = make_nibbit(); e.hp = e.max_hp = 500
eng = CombatEngine([p], [e], seed=1)
eng.start_player_turn()
drum = fresh('Drum of Battle')
p.draw_pile = [fresh('Bludgeon') for _ in range(20)]
p.hand = [drum]
eng.play_card(p, drum)          # play 1 -> registers hook
p.discard_pile.remove(drum)
p.hand.append(drum)
eng.play_card(p, drum)          # play 2 -> registers a SECOND hook
energy_before = p.energy
eng.exhaust_card(p, drum)       # should grant +2 once, not +4
check("Drum of Battle grants energy once per PLAY, not once per exhaust",
      p.energy - energy_before > 2,
      f"energy gained on single exhaust after 2 plays = {p.energy - energy_before} (expect 2)")


print("\n" + "=" * 60)
confirmed = [r for r in results if r[1]]
print(f"{len(confirmed)} / {len(results)} suspected issues CONFIRMED")
