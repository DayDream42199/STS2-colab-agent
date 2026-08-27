"""Thorns verification for task #34. Every assertion below is either a
wiki-sourced number or an explicitly-reasoned engine rule (see the
_retaliate_thorns docstring in entities.py)."""
import os
import sys

# The modules under test live one directory up. This used to be a hardcoded
# absolute path, which is why the whole suite only ran on one machine from
# one directory -- and why it lived in a temp folder rather than the repo.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from game_engine.entities import Player
from game_engine.enemies import (Enemy, Move, IntentType, make_nibbit, make_toadpole,
                     make_toadpole_pair, _dmg_move)
from game_engine.combat import CombatEngine
from game_engine.cards import CARD_POOL_IRONCLAD, make_starter_deck
from game_engine.statuses import StatusType
from game_engine.potions import POTION_POOL_IRONCLAD
from game_engine.relics import RELIC_POOL_IRONCLAD

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  [{'ok' if ok else 'FAIL'}] {label}: got {got!r}, want {want!r}")
    if not ok:
        FAILS.append(label)


def card(name):
    for f in CARD_POOL_IRONCLAD:
        c = f()
        if c.name == name:
            return c
    # Basic cards (Strike/Defend/Bash) aren't in the reward pool
    for c in make_starter_deck():
        if c.name == name:
            return c
    raise KeyError(name)


def bag(hp=1000):
    e = make_nibbit()
    e.max_hp = e.hp = hp
    return e


def setup(player_hp=500, enemy=None):
    p = Player("Tester", player_hp, 99, deck=make_starter_deck())
    e = enemy if enemy is not None else bag()
    eng = CombatEngine([p], [e], seed=1, scale_enemies=False)
    eng.start_player_turn()
    p.energy = 99
    return eng, p, e


print("=" * 70)
print("1. Fires PER HIT, not per card (the Skittish contrast)")
print("=" * 70)
eng, p, e = setup()
e.add_status(StatusType.THORNS, 2)
p.hand = [card("Twin Strike")]
hp0 = p.hp
eng.play_card(p, p.hand[0], target=e)
check("Twin Strike (2 hits) into 2 Thorns costs the player", hp0 - p.hp, 4)
check("Thorns stacks are NOT spent by triggering", e.get_status(StatusType.THORNS), 2)

eng, p, e = setup()
e.add_status(StatusType.THORNS, 2)
p.hand = [card("Strike")]
hp0 = p.hp
eng.play_card(p, p.hand[0], target=e)
check("single-hit Strike into 2 Thorns costs the player", hp0 - p.hp, 2)

print()
print("=" * 70)
print("2. 'When HIT', not 'when it loses HP'")
print("=" * 70)
eng, p, e = setup()
e.add_status(StatusType.THORNS, 3)
e.block = 100
p.hand = [card("Strike")]
hp0, ehp0 = p.hp, e.hp
eng.play_card(p, p.hand[0], target=e)
check("fully blocked attack still retaliates", hp0 - p.hp, 3)
check("...and the enemy really took no HP damage", e.hp, ehp0)

eng, p, e = setup(enemy=bag(hp=1))
e.add_status(StatusType.THORNS, 3)
p.hand = [card("Strike")]
hp0 = p.hp
eng.play_card(p, p.hand[0], target=e)
check("killing blow still retaliates", hp0 - p.hp, 3)
check("...and the enemy is dead", e.alive, False)

print()
print("=" * 70)
print("3. Retaliation is not itself an attack (no infinite bounce)")
print("=" * 70)
eng, p, e = setup()
e.add_status(StatusType.THORNS, 3)
p.add_status(StatusType.THORNS, 5)
p.hand = [card("Strike")]
hp0, ehp0 = p.hp, e.hp
eng.play_card(p, p.hand[0], target=e)
check("player takes the enemy's Thorns", hp0 - p.hp, 3)
check("enemy takes ONLY the Strike, not a bounced 5", ehp0 - e.hp, 6)

eng, p, e = setup()
e.add_status(StatusType.THORNS, 3)
e.add_status(StatusType.VULNERABLE, 3)
p.add_status(StatusType.STRENGTH, 10)
p.hand = [card("Strike")]
hp0 = p.hp
eng.play_card(p, p.hand[0], target=e)
check("Thorns damage ignores Strength/Vulnerable (flat 3)", hp0 - p.hp, 3)

print()
print("=" * 70)
print("4. Only real attacks retaliate")
print("=" * 70)
eng, p, e = setup()
e.add_status(StatusType.THORNS, 3)
fire = next(x for x in POTION_POOL_IRONCLAD if x.name == "Fire Potion")
p.potions = [fire]
hp0 = p.hp
eng.use_potion(p, fire, target=e)
check("Fire Potion (not an attack) draws no retaliation", hp0 - p.hp, 0)

eng, p, e = setup()
p.add_status(StatusType.THORNS, 4)
p.add_status(StatusType.POISON, 5)
hp0 = p.hp
p.tick_start_of_turn(eng.log)
check("own poison tick draws no self-retaliation", hp0 - p.hp, 5)

print()
print("=" * 70)
print("5. Block absorbs retaliation; Artifact does not eat it")
print("=" * 70)
eng, p, e = setup()
e.add_status(StatusType.THORNS, 3)
p.block = 10
p.hand = [card("Strike")]
hp0 = p.hp
eng.play_card(p, p.hand[0], target=e)
check("retaliation hits Block first", p.block, 7)
check("...and no HP is lost", p.hp, hp0)

eng, p, e = setup()
p.add_status(StatusType.ARTIFACT, 1)
p.add_status(StatusType.THORNS, 3)
check("Artifact does not negate Thorns (it is a buff)", p.get_status(StatusType.THORNS), 3)
check("...and no Artifact stack was spent", p.get_status(StatusType.ARTIFACT), 1)

print()
print("=" * 70)
print("6. Thorns is Permanent (survives turn boundaries)")
print("=" * 70)
eng, p, e = setup()
p.add_status(StatusType.THORNS, 3)
eng.end_player_turn()
eng.run_enemy_turn()
eng.start_player_turn()
check("player Thorns after a full round", p.get_status(StatusType.THORNS), 3)

print()
print("=" * 70)
print("7. Enemy attacks eat the PLAYER's Thorns, per hit")
print("=" * 70)
# 3-hit enemy move vs a player holding 2 Thorns -> enemy should take 6.
def _triple(engine, enemy):
    t = engine.pick_enemy_attack_target()
    for _ in range(3):
        t.take_damage(enemy.deal_attack_damage(1), log=engine.log,
                      label=enemy.name, attacker=enemy)
triple = Move("Triple Poke", IntentType.ATTACK, _triple, damage=1)
tri_enemy = Enemy("Tripler", 200, [triple], lambda e, t: triple)
eng, p, e = setup(enemy=tri_enemy)
p.add_status(StatusType.THORNS, 2)
ehp0 = e.hp
eng.end_player_turn()
eng.run_enemy_turn()
check("enemy 3-hit move into player's 2 Thorns", ehp0 - e.hp, 6)

print()
print("=" * 70)
print("8. Toadpole: wiki cycle Whirl -> Spiken -> Spike Spit")
print("=" * 70)
tp = make_toadpole()
check("Toadpole HP in wiki range 21-25", 21 <= tp.max_hp <= 25, True)
eng, p, e = setup(enemy=tp)
hp0 = p.hp
eng.end_player_turn(); eng.run_enemy_turn()
check("turn 1 Whirl deals 7", hp0 - p.hp, 7)
check("no Thorns yet", e.get_status(StatusType.THORNS), 0)

eng.start_player_turn(); p.block = 0
hp1 = p.hp
eng.end_player_turn(); eng.run_enemy_turn()
check("turn 2 Spiken grants 2 Thorns", e.get_status(StatusType.THORNS), 2)
check("...and deals no damage", hp1 - p.hp, 0)

eng.start_player_turn(); p.block = 0
hp2 = p.hp
eng.end_player_turn(); eng.run_enemy_turn()
check("turn 3 Spike Spit deals 3x3", hp2 - p.hp, 9)
check("...and strips its own 2 Thorns", e.get_status(StatusType.THORNS), 0)

print()
print("  -- and the trap the cycle is built around --")
tp = make_toadpole()
eng, p, e = setup(enemy=tp)
e.add_status(StatusType.THORNS, 2)          # as if it had just used Spiken
p.hand = [card("Twin Strike"), card("Strike")]
hp0 = p.hp
eng.play_card(p, p.hand[0], target=e)
eng.play_card(p, p.hand[0], target=e)
check("Twin Strike then Strike into 2 Thorns = 3 hits = 6", hp0 - p.hp, 6)

pair = make_toadpole_pair()
check("Toadpoles (Weak) is a pair", len(pair), 2)
check("front Toadpole opens on Spiken", pair[0]._choose_move(pair[0], 0).name, "Spiken")
check("back Toadpole opens on Whirl", pair[1]._choose_move(pair[1], 0).name, "Whirl")

print()
print("=" * 70)
print("9. New Thorns sources")
print("=" * 70)
lb = next(x for x in POTION_POOL_IRONCLAD if x.name == "Liquid Bronze")
check("Liquid Bronze rarity", lb.rarity, "Uncommon")
eng, p, e = setup()
p.potions = [lb]
eng.use_potion(p, lb)
check("Liquid Bronze grants 3 Thorns", p.get_status(StatusType.THORNS), 3)

scales = next(r for r in RELIC_POOL_IRONCLAD if r.name == "Bronze Scales")
check("Bronze Scales rarity", scales.rarity, "Common")
p = Player("Relic Tester", 100, 3, deck=make_starter_deck())
p.add_relic(scales)
eng = CombatEngine([p], [bag()], seed=1, scale_enemies=False)
eng.start_player_turn()
check("Bronze Scales grants 3 Thorns at combat start", p.get_status(StatusType.THORNS), 3)
eng.end_player_turn(); eng.run_enemy_turn(); eng.start_player_turn()
check("...and does NOT re-grant on turn 2", p.get_status(StatusType.THORNS), 3)

print()
print("=" * 70)
if FAILS:
    print(f"{len(FAILS)} FAILURE(S): {FAILS}")
    sys.exit(1)
print("ALL THORNS CHECKS PASSED")
