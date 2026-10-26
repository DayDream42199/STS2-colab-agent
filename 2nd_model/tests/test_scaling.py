"""Every scripted enemy, 1 to 4 players, both act factors: what scales and what
must not.

Real STS2 co-op: HP x players x act (2 -> x2.2 in act 1), Block flat x2 for
two players and x players x act beyond, Artifact +1 per extra player - and
NOTHING else. An enemy's damage, the Strength it gains and the status cards it
hands out are the same numbers whether one player is there or four, and every
move lands on every living player, so each of them takes what a solo player
would. Which move comes next does not depend on the party either.
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
    for a in allies:
        a.deck = ["strike"] * 5 + ["defend"] * 4 + ["bash"]    # not whatever TestAlly1 holds today
    foe = create_enemy(kind, "e1", rng=random.Random(seed))
    c = Combat(allies, [foe], rng=random.Random(seed), act=act, scale_enemies=scale)
    c.start()
    for a in allies:
        a.max_hp = a.current_hp = HP
        a.block = 0
        # Deep enough that nothing is reshuffled in TURNS turns, so a card the
        # enemy handed out is still in the discard or draw pile when counted.
        a.draw_pile = [CardRef("strike") for _ in range(60)]
    return c, allies, foe


def play(kind, players, act, seed, scale=True):
    """Per turn: (move, HP lost by each player, enemy Block after, enemy
    Strength after, status cards handed out so far to each player)."""
    c, a, foe = fight(kind, players, act, seed, scale)
    rows = []
    for _ in range(TURNS):
        move = foe.intent["name"]
        before = {p.unit_id: p.current_hp for p in a}
        for p in a:
            # Into the discard, not away: the enemy's cards may have been drawn.
            p.discard_pile.extend(p.hand)
            p.hand = []
        c.end_player_turn()
        for p in a:
            # Debuffs off between turns, so damage is the printed number
            # (and The Insatiable's Sandpit does not eat the party).
            p.statuses.clear()
        strength = foe.get_status("strength")
        lost = [before[p.unit_id] - p.current_hp for p in a]
        handed = [sum(1 for r in p.hand + p.draw_pile + p.discard_pile
                      if r not in ("strike", "defend", "bash")) for p in a]
        rows.append((move, lost, foe.block, strength.amount if strength else 0, handed))
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
            check("%s: every player takes exactly what a solo player takes" % label,
                  [r[1] for r in rows] == [[s[1][0]] * players for s in solo],
                  ([r[1] for r in rows], [s[1][0] for s in solo]))
            check("%s: Strength is not scaled" % label,
                  [r[3] for r in rows] == [r[3] for r in solo], [r[3] for r in rows])
            check("%s: every player gets the solo number of status cards" % label,
                  [r[4] for r in rows] == [[s[4][0]] * players for s in solo],
                  ([r[4] for r in rows], [s[4][0] for s in solo]))

            scale = block_scale(players, act)
            check("%s: Block x%.1f, rounded" % (label, scale),
                  [r[2] for r in rows] == [round(s[2] * scale) for s in solo],
                  ([r[2] for r in rows], [round(s[2] * scale) for s in solo]))

            artifact = foe.get_status("artifact")
            solo_artifact = create_enemy(kind, "e1").__class__.__dict__.get("ARTIFACT")
            if solo_artifact:
                c2, _, foe2 = fight(kind, players, act, 1)
                check("%s: Artifact %d + 1 per extra player" % (label, solo_artifact),
                      foe2.get_status("artifact").amount == solo_artifact + players - 1,
                      foe2.get_status("artifact").amount)
            solo_slippery = create_enemy(kind, "e1").__class__.__dict__.get("SLIPPERY")
            if solo_slippery:
                c3, _, foe3 = fight(kind, players, act, 1)
                check("%s: Slippery %d x players" % (label, solo_slippery),
                      foe3.get_status("slippery").amount == solo_slippery * players,
                      foe3.get_status("slippery").amount)

# --- the intent tells the truth about Block -----------------------------------
# Whatever Block an enemy announces is what it ends up with, at every party
# size. Dummy1 announced 2 and gained 4 with two players: the Block was scaled
# and the intent was not. Dummy1 puts it in "amount" on a block intent; the
# scripted enemies carry it in "block", on attacks that guard as they swing too.
def announced_block(enemy):
    intent = enemy.intent or {}
    if "block" in intent:
        return intent["block"]
    return intent.get("amount", 0) if intent.get("type") == "block" else 0

for kind in known_enemy_type_ids():
    for players in (1, 2, 3, 4):
        c, a, foe = fight(kind, players, "act1", 3)
        told, got = [], []
        for _ in range(TURNS):
            told.append(announced_block(foe))
            for p in a:
                p.hand = []
            c.end_player_turn()
            for p in a:
                p.statuses.clear()
            got.append(foe.block)          # gained this enemy phase; cleared at its next
        check("%s %dp: Block announced == Block gained, every turn" % (kind, players),
              told == got, (told, got))

c, a, foe = fight("dummy1", 2, "act1", 1)
for p in a:
    p.hand = []
c.end_player_turn()                                   # turn 1 attack; turn 2 is the block
check("the reported case: Dummy1 with two players announces 4 Block, not 2",
      foe.intent == {"type": "block", "amount": 4}, foe.intent)

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
