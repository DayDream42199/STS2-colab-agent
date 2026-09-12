"""Every scripted enemy, 1 to 4 players, both act factors: what scales and what
must not.

Real STS2 co-op, as the reference has it: HP x players x act (2 -> x2.2 in act
1), Block flat x2 for two players and x players x act beyond, and NOTHING else
- an enemy's damage, the Strength it gains and the status cards it hands out
are the same numbers whether one player is there or four. Each move names one
living player and only that player is hit.
"""
import random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import create_ally, create_enemy, known_enemy_type_ids
from GameEngine.Units.Enemies._scripted import ScriptedEnemy, ACT_SCALING, hp_scale, block_scale
from GameEngine.Cards._card_ref import CardRef

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))

TURNS = 6
HP = 500

SCRIPTED = [k for k in known_enemy_type_ids()
            if isinstance(create_enemy(k, "x"), ScriptedEnemy)]


def fight(kind, players, act, seed, scale=True):
    allies = [create_ally("testally1", "p%d" % (i + 1), rng=random.Random(seed + i))
              for i in range(players)]
    foe = create_enemy(kind, "e1", rng=random.Random(seed))
    c = Combat(allies, [foe], rng=random.Random(seed), act=act, scale_enemies=scale)
    c.start()
    for a in allies:
        a.max_hp = a.current_hp = HP
        a.block = 0
        # Deep enough that nothing is reshuffled in TURNS turns, so a card the
        # enemy handed out is still in the discard (or, for The Insatiable's
        # bottom-of-pile escapes, the draw pile) when we count it.
        a.draw_pile = [CardRef("strike") for _ in range(60)]
    return c, allies, foe


def play(kind, players, act, seed, scale=True):
    """Per turn: (move, who was named, HP lost by everyone, enemy Block after,
    enemy Strength after, status cards handed out so far per player)."""
    c, a, foe = fight(kind, players, act, seed, scale)
    rows = []
    for _ in range(TURNS):
        move, named = foe.intent["name"], foe.intent.get("target")
        before = {p.unit_id: p.current_hp for p in a}
        for p in a:
            p.hand = []
        c.end_player_turn()
        for p in a:
            # Debuffs off between turns, so damage is the printed number and
            # comparable across party sizes: solo, a Roar's Vulnerable always
            # lands on the one player the next hit finds; with four it may
            # not. (Also keeps The Insatiable's Sandpit from eating the party.)
            p.statuses.clear()
        strength = foe.get_status("strength")
        lost = {p.unit_id: before[p.unit_id] - p.current_hp for p in a}
        handed = tuple(sum(1 for r in p.draw_pile + p.discard_pile if r != "strike") for p in a)
        rows.append((move, named, lost, foe.block,
                     strength.amount if strength else 0, handed))
    return c, a, foe, rows


for kind in SCRIPTED:
    print("--", kind)
    solo_hp = create_enemy(kind, "e1", rng=random.Random(1)).max_hp
    _, _, _, solo = play(kind, 1, "act1", 1)

    for act in ("act1", "act2"):
        for players in (1, 2, 3, 4):
            c, a, foe, rows = play(kind, players, act, 1)
            label = "%s %dp %s" % (kind, players, act)

            want_hp = solo_hp if players == 1 else max(1, round(solo_hp * hp_scale(players, act)))
            check("%s: HP %d -> %d" % (label, solo_hp, want_hp), foe.max_hp == want_hp, foe.max_hp)

            # the script is the script, whoever is there
            check("%s: same moves as solo" % label,
                  [r[0] for r in rows] == [r[0] for r in solo],
                  [r[0] for r in rows])
            check("%s: damage is not scaled" % label,
                  [sum(r[2].values()) for r in rows] == [sum(r[2].values()) for r in solo],
                  ([sum(r[2].values()) for r in rows], [sum(r[2].values()) for r in solo]))
            check("%s: Strength is not scaled" % label,
                  [r[4] for r in rows] == [r[4] for r in solo], [r[4] for r in rows])
            # Liquify Ground gives every player the same six; everything else
            # gives one named player the solo number. Neither grows with the party.
            per_fight = players if kind == "theinsatiable" else 1
            check("%s: status cards handed out are not scaled" % label,
                  [sum(r[5]) for r in rows] == [s[5][0] * per_fight for s in solo],
                  ([sum(r[5]) for r in rows], [s[5][0] * per_fight for s in solo]))

            scale = block_scale(players, act)
            check("%s: Block x%.1f, rounded" % (label, scale),
                  [r[3] for r in rows] == [round(s[3] * scale) for s in solo],
                  ([r[3] for r in rows], [round(s[3] * scale) for s in solo]))

            # only the named player is hit
            for move, named, lost, _, _, _ in rows:
                hit = [uid for uid, n in lost.items() if n > 0]
                if hit:
                    check("%s: %s hit only %s, who was named" % (label, move, named),
                          hit == [named], (hit, named))

    # four players, many fights: everyone gets picked on
    named = set()
    for seed in range(30):
        c, a, foe = fight(kind, 4, "act1", seed)
        named.add(foe.intent.get("target"))
        for _ in range(3):
            for p in a:
                p.hand = []
            c.end_player_turn()
            for p in a:
                p.statuses.clear()
            named.add(foe.intent.get("target"))
    named.discard(None)
    check("%s: over 30 four-player fights every player gets named" % kind,
          named == {"p1", "p2", "p3", "p4"}, sorted(named))

# scaling off means off, whatever the party size
c, a, foe = fight("nibbit", 4, "act2", 1, scale=False)
solo_hp = create_enemy("nibbit", "e1", rng=random.Random(1)).max_hp
for p in a:
    p.hand = []
c.end_player_turn(); c.end_player_turn()          # Butt, then Hesitant Slice (5 Block)
check("scale_enemies=False: four players, Nibbit keeps %d HP and blocks 5" % solo_hp,
      foe.max_hp == solo_hp and foe.block == 5, (foe.max_hp, foe.block))

# the multipliers themselves, against the reference table
r6 = lambda *xs: tuple(round(x, 6) for x in xs)
check("hp_scale: 1p 1.0, 2p act1 2.2, 3p act2 3.6, 4p act3boss 5.2",
      r6(hp_scale(1), hp_scale(2), hp_scale(3, "act2"), hp_scale(4, "act3boss"))
      == (1.0, 2.2, 3.6, 5.2))
check("block_scale: 1p 1.0, 2p 2.0 flat (no act), 3p act1 3.3, 4p act2 4.8",
      r6(block_scale(1), block_scale(2, "act3boss"), block_scale(3), block_scale(4, "act2"))
      == (1.0, 2.0, 3.3, 4.8))

print()
print("%d checks failed" % len(bad))
for label in bad:
    print("   ", label)

import sys as _sys
_sys.exit(1 if bad else 0)
