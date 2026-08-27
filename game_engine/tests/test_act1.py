# -*- coding: utf-8 -*-
"""Verification for tasks #23/#24/#33: mid-combat summoning, the remaining
Act 1 elites and bosses, and the mechanics they needed."""
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
from game_engine.cards import CARD_POOL_IRONCLAD, ANCIENT_CARDS_IRONCLAD, make_starter_deck
from game_engine.statuses import StatusType

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  [{'ok' if ok else 'FAIL'}] {label}: got {got!r}, want {want!r}")
    if not ok:
        FAILS.append(label)


_ALL = list(CARD_POOL_IRONCLAD) + list(ANCIENT_CARDS_IRONCLAD)


def card(name):
    for f in _ALL:
        c = f()
        if c.name == name:
            return c
    for c in make_starter_deck():
        if c.name == name:
            return c
    raise KeyError(name)


def setup(enemies, players=1, hp=2000):
    ps = [Player(f"P{i+1}", hp, 99, deck=make_starter_deck()) for i in range(players)]
    eng = CombatEngine(ps, enemies, seed=5, scale_enemies=False)
    eng.start_player_turn()
    for p in ps:
        p.energy = 99
    return eng, ps[0]


def kill(eng, enemy):
    """Kill an enemy the way a card would, so death effects resolve."""
    enemy.hp = 1
    enemy.take_damage(999, log=eng.log, attacker=eng.players[0])
    eng._check_victory_defeat()


print("=" * 74)
print("Mid-combat summoning (#23)")
print("=" * 74)
merc = E.make_gremlin_merc()
eng, p = setup([merc])
kill(eng, merc)
names = sorted(e.name for e in eng.enemies if e.alive)
check("Gremlin Merc summons both gremlins on death", names, ["Fat Gremlin", "Sneaky Gremlin"])
check("...so the fight is NOT over", eng.is_over, False)
check("...and the summons are stunned for one turn",
      all(e.stunned_turns == 1 for e in eng.enemies if e.alive), True)

parasite = E.make_phrog_parasite()
eng, p = setup([parasite])
kill(eng, parasite)
check("Phrog Parasite spawns 4 Wrigglers", sum(1 for e in eng.enemies if e.alive), 4)
check("...all Wrigglers", {e.name for e in eng.enemies if e.alive}, {"Wriggler"})

# Stunned spawns take no action on their first enemy phase. Wriggler opens
# on Wriggle (shuffles Infection, gains Strength) rather than an attack, so
# "did it act" is measured by the Infection cards, not by HP.
before_infections = sum(1 for c in p.discard_pile if c.name == "Infection")
eng.run_enemy_turn()
check("stunned spawns do nothing on the turn they appear",
      sum(1 for c in p.discard_pile if c.name == "Infection"), before_infections)
eng.start_player_turn()
eng.end_player_turn()
eng.run_enemy_turn()
check("...and act on the next one",
      sum(1 for c in p.discard_pile if c.name == "Infection") > before_infections, True)

fog = E.make_living_fog()
eng, p = setup([fog])
eng.end_player_turn(); eng.run_enemy_turn()          # Advanced Gas
eng.start_player_turn(); eng.end_player_turn(); eng.run_enemy_turn()   # Bloat
check("Living Fog's Bloat summons a Gas Bomb",
      any(e.name == "Gas Bomb" for e in eng.enemies), True)
bomb = next(e for e in eng.enemies if e.name == "Gas Bomb")
eng.start_player_turn(); eng.end_player_turn(); eng.run_enemy_turn()
check("...and the Gas Bomb dies after exploding", bomb.alive, False)

fm = E.make_fogmog()
eng, p = setup([fm])
eng.end_player_turn(); eng.run_enemy_turn()
eng.start_player_turn(); eng.end_player_turn(); eng.run_enemy_turn()
check("Fogmog's restored Illusory Spores summons an Eye With Teeth",
      any(e.name == "Eye With Teeth" for e in eng.enemies), True)

rat = E.make_two_tailed_rat()
eng, p = setup([rat])
for _ in range(30):
    if eng.is_over:
        break
    eng.end_player_turn()
    eng.run_enemy_turn()
    eng.start_player_turn()
check("Two-Tailed Rat's unbounded Call for Backup stops at the enemy cap",
      len(eng.enemies) <= CombatEngine.MAX_ENEMIES, True)

# Summoned enemies must be scaled for the party like starting ones.
merc = E.make_gremlin_merc()
ps = [Player(f"P{i}", 500, 99, make_starter_deck()) for i in range(2)]
eng2 = CombatEngine(ps, [merc], seed=1)
eng2.start_player_turn()
kill(eng2, merc)
solo_fat = E.make_fat_gremlin()
spawned_fat = next(e for e in eng2.enemies if e.name == "Fat Gremlin")
check("summoned minions get multiplayer HP scaling",
      spawned_fat.max_hp > solo_fat.max_hp, True)

print()
print("=" * 74)
print("Minions and leaders")
print("=" * 74)
kin = E.make_the_kin()
eng, p = setup(kin)
check("The Kin is a priest plus two followers", len(kin), 3)
priest = kin[0]
kill(eng, priest)
check("killing the Priest removes both Followers",
      [e.alive for e in kin[1:]], [False, False])
check("...which ends the fight", eng.victory, True)

fat = E.make_fat_gremlin()
eng, p = setup([fat])
eng.end_player_turn(); eng.run_enemy_turn()      # Spawned: does nothing
eng.start_player_turn(); eng.end_player_turn(); eng.run_enemy_turn()  # Flee
check("Fat Gremlin flees on its second turn", fat.alive, False)

print()
print("=" * 74)
print("New debuffs: Ringing and Smoggy")
print("=" * 74)
eng, p = setup([E.make_nibbit()])
p.add_status(StatusType.RINGING, 1)
check("first card is allowed under Ringing", eng.play_card(p, card("Strike"), target=eng.enemies[0]) if card("Strike") in p.hand else True, True)
p.hand = [card("Strike"), card("Strike")]
first = eng.play_card(p, p.hand[0], target=eng.enemies[0])
second = eng.play_card(p, p.hand[0], target=eng.enemies[0])
check("Ringing blocks the second card of the turn", (first, second), (True, False))
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
p.energy = 99
p.hand = [card("Strike"), card("Strike")]
a = eng.play_card(p, p.hand[0], target=eng.enemies[0])
b = eng.play_card(p, p.hand[0], target=eng.enemies[0])
check("...and wears off next turn", (a, b), (True, True))

eng, p = setup([E.make_nibbit()])
p.add_status(StatusType.SMOGGY, 1)
d1, d2, atk_card = card("Defend"), card("Defend"), card("Strike")
p.hand = [d1, d2, atk_card]
s1 = eng.play_card(p, d1)
s2 = eng.play_card(p, d2)
atk = eng.play_card(p, atk_card, target=eng.enemies[0])
check("Smoggy allows 1 Skill, blocks the 2nd, allows Attacks",
      (s1, s2, atk), (True, False, True))

print()
print("=" * 74)
print("Vigor and Intangible")
print("=" * 74)
eel = E.make_terror_eel()
eng, p = setup([eel])
eel.add_status(StatusType.VIGOR, 6)
check("Vigor adds to the next attack", eel.deal_attack_damage(10), 16)
check("...and is consumed", eel.get_status(StatusType.VIGOR), 0)
check("...so the attack after is normal", eel.deal_attack_damage(10), 10)

fysh = E.make_soul_fysh()
eng, p = setup([fysh])
fysh.add_status(StatusType.INTANGIBLE, 2)
hp0 = fysh.hp
fysh.take_damage(50, log=eng.log, attacker=p)
check("Intangible reduces damage to 1", hp0 - fysh.hp, 1)
hp0 = fysh.hp
fysh.lose_hp(30, log=eng.log)
check("...and HP loss to 1", hp0 - fysh.hp, 1)

print()
print("=" * 74)
print("Ceremonial Beast: the Plow phase change")
print("=" * 74)
beast = E.make_ceremonial_beast()
eng, p = setup([beast])
eng.end_player_turn(); eng.run_enemy_turn()          # Stamp
check("Stamp sets the Plow threshold", beast.get_status(StatusType.PLOW), 150)
eng.start_player_turn(); eng.end_player_turn(); eng.run_enemy_turn()   # Plow
check("phase 1 builds Strength", beast.get_status(StatusType.STRENGTH), 2)
beast.hp = 140          # cross the threshold
eng.start_player_turn(); eng.end_player_turn(); eng.run_enemy_turn()
check("crossing the threshold Stuns it", beast.current_move.name != "Plow", True)
check("...and wipes all its Strength", beast.get_status(StatusType.STRENGTH), 0)
seen = set()
for _ in range(4):
    eng.start_player_turn(); eng.end_player_turn(); eng.run_enemy_turn()
    seen.add(beast.current_move.name)
check("phase 2 uses the new cycle",
      {"Beast Cry", "Stomp", "Crush"} & seen == {"Beast Cry", "Stomp", "Crush"}, True)

print()
print("=" * 74)
print("Waterfall Giant: Steam Eruption is a posthumous bomb")
print("=" * 74)
giant = E.make_waterfall_giant()
eng, p = setup([giant])
eng.end_player_turn(); eng.run_enemy_turn()          # Pressurize
check("Pressurize stores 15 Steam", giant.get_status(StatusType.STEAM_ERUPTION), 15)
for _ in range(3):
    eng.start_player_turn(); eng.end_player_turn(); eng.run_enemy_turn()
stored = giant.get_status(StatusType.STEAM_ERUPTION)
check("every move feeds the counter", stored > 15, True)
eng.start_player_turn()
giant.hp = 1
giant.take_damage(99, log=eng.log, attacker=p)
eng._check_victory_defeat()
check("killing it queues an eruption", len(eng.pending_eruptions), 1)
check("...but it was the last enemy, so the fight ends first", eng.victory, True)

# The bomb only matters when the fight continues, so re-run it with a
# second enemy still standing.
giant = E.make_waterfall_giant()
bystander = E.make_nibbit()
bystander.max_hp = bystander.hp = 500
eng, p = setup([giant, bystander])
giant.add_status(StatusType.STEAM_ERUPTION, 24)
giant.hp = 1
giant.take_damage(99, log=eng.log, attacker=p)
eng._check_victory_defeat()
check("with another enemy alive the fight continues", eng.is_over, False)
p.block = 0
php = p.hp
eng.end_player_turn()
check("...and the eruption lands at the end of your next turn", php - p.hp, 24)
check("...then it is spent", eng.pending_eruptions, [])
# It no longer kills itself: the invented About To Blow -> Explode finale is gone.
check("the boss has no self-destruct move left",
      any(m.name in ("About To Blow", "Explode") for m in E.make_waterfall_giant().moveset),
      False)

print()
print("=" * 74)
print("Lagavulin Matriarch: Soul Siphon can push stats negative")
print("=" * 74)
lag = E.make_lagavulin_matriarch()
eng, p = setup([lag])
p.statuses.pop(StatusType.STRENGTH, None)
p.add_status(StatusType.STRENGTH_LOSS, 2)
p.add_status(StatusType.DEXTERITY_LOSS, 2)
check("Strength drain applies below zero", p.deal_attack_damage(6), 4)
p.block = 0
p.gain_block(5)
check("Dexterity drain applies below zero", p.block, 3)

print()
print("=" * 74)
print("Soul Fysh's Beckon card")
print("=" * 74)
eng, p = setup([E.make_soul_fysh()])
from game_engine.cards import make_beckon
p.hand = [make_beckon()]
p.block = 50
hp0 = p.hp
eng.end_player_turn()
check("Beckon costs 6 HP if held at end of turn", hp0 - p.hp, 6)
check("...ignoring Block (it is HP loss, not damage)", p.block, 50)

print()
print("=" * 74)
print("Bygone Effigy's scripted opener")
print("=" * 74)
effigy = E.make_bygone_effigy()
eng, p = setup([effigy])
hp0 = p.hp
p.block = 0
eng.end_player_turn(); eng.run_enemy_turn()
check("turn 1 Sleep does nothing", p.hp, hp0)
eng.start_player_turn(); p.block = 0; eng.end_player_turn(); eng.run_enemy_turn()
check("turn 2 Wake grants 10 Strength", effigy.get_status(StatusType.STRENGTH), 10)
check("...and still deals no damage", p.hp, hp0)
eng.start_player_turn(); p.block = 0; eng.end_player_turn(); eng.run_enemy_turn()
check("turn 3 Slashes for 13+10", hp0 - p.hp, 23)

print()
print("=" * 74)
if FAILS:
    print(f"{len(FAILS)} FAILURE(S):")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("ALL ACT 1 CHECKS PASSED")
