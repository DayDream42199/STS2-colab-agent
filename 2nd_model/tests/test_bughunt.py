"""Empirical bug hunt against the current engine."""
import random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from session import Session
from Protocol.protocol import encode
from Protocol.enums import ClientMessage, ServerMessage
from GameEngine.Combat.combat import Combat, CombatPhase
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Effects.StatusEffects.vulnerable import Vulnerable
from GameEngine.Effects.InstantEffects.instant_damage import InstantDamage
from GameEngine.Resolution.resolver import Resolver

bugs = []
def report(label, is_bug, detail=""):
    tag = "BUG " if is_bug else "ok  "
    if is_bug: bugs.append(label)
    print(f"[{tag}] {label}{(' -> ' + str(detail)) if detail else ''}")

def fight(n_allies=1, n_enemies=1, seed=1):
    allies = [create_ally("testally1", f"p{i+1}", rng=random.Random(seed)) for i in range(n_allies)]
    enemies = [create_enemy("dummy1", f"e{i+1}", rng=random.Random(seed)) for i in range(n_enemies)]
    c = Combat(allies, enemies, rng=random.Random(seed))
    c.start()
    return c, allies, enemies


# --- 1. can a dead ally still play cards? ------------------------------------
c, allies, enemies = fight()
a, e = allies[0], enemies[0]
a.current_hp = 0
a.hand = ["strike"]
a.energy = 3
e.current_hp = e.max_hp = 50
hp_before = e.current_hp
try:
    c.play_card(a, 0, target=e)
    report("a dead ally can still play cards", e.current_hp < hp_before,
           f"ally hp={a.current_hp}, enemy {hp_before}->{e.current_hp}")
except Exception as err:
    report("a dead ally can still play cards", False, f"blocked: {type(err).__name__}: {err}")

# --- 2. does Session let a dead player act? ----------------------------------
s = Session(combat_factory=Combat, required_players=1, rng=random.Random(3))
s.add_player("s1")
ally = s.ally_for("s1")
ally.current_hp = 0
ally.hand = ["strike"]
ally.energy = 3
out = s.handle("s1", encode(ClientMessage.PLAY_CARD, hand_index=0,
                            target_id=s.combat.enemies[0].unit_id))
was_error = any(m["type"] == ServerMessage.ERROR.value for _, m in out)
report("Session lets a dead player act", not was_error,
       [m["type"] for _, m in out])

# --- 3. enemy block: cleared each enemy turn, or accumulating? ---------------
c, allies, enemies = fight(seed=5)
e = enemies[0]
blocks = []
for _ in range(6):
    if c.is_over(): break
    c.end_player_turn()
    blocks.append(e.block)
report("enemy block accumulates across turns", len(set(blocks)) > 1 and max(blocks) > 2,
       f"block after each turn: {blocks}")

# --- 4. multi-enemy: stale fallback target after a death ---------------------
c, allies, enemies = fight(n_allies=2, n_enemies=3, seed=7)
for e in enemies:
    e.intent = {"type": "attack", "amount": 200}
allies[0].current_hp = 1
c.end_player_turn()
survivors = [a.unit_id for a in allies if a.is_alive()]
report("multi-enemy all hit the same fallback ally",
       len(survivors) == 1 and allies[1].is_alive(),
       f"p1 hp={allies[0].current_hp} p2 hp={allies[1].current_hp}; "
       f"3 enemies x200 dmg, survivors={survivors}")

# --- 5. status applied to an already-dead enemy ------------------------------
c, allies, enemies = fight(seed=11)
a, e = allies[0], enemies[0]
e.current_hp = 1
a.hand = ["bash"]
a.energy = 3
c.play_card(a, 0, target=e)
report("status lands on a corpse", not e.is_alive() and "vulnerable" in e.statuses,
       f"enemy hp={e.current_hp} statuses={ {k: v.amount for k, v in e.statuses.items()} }")

# --- 6. partial application if an effect fails mid-list ----------------------
class Boom:
    effect_id = "boom"
c, allies, enemies = fight(seed=13)
a, e = allies[0], enemies[0]
e.current_hp = e.max_hp = 50
a.hand = ["strike"]
a.energy = 3
hand_len, energy_before = len(a.hand), a.energy
orig = Resolver.resolve
def exploding(effect):
    orig(effect)
    raise NotImplementedError("simulated resolver failure")
Resolver.resolve = staticmethod(exploding)
try:
    c.play_card(a, 0, target=e)
except NotImplementedError:
    pass
finally:
    Resolver.resolve = orig
report("failed resolve leaves card in hand AND damage applied",
       e.current_hp < 50 and len(a.hand) == hand_len and a.energy == energy_before,
       f"enemy hp={e.current_hp}, hand={len(a.hand)}, energy={a.energy} (card replayable)")

# --- 7. dead ally keeps hand and never redraws ------------------------------
c, allies, enemies = fight(n_allies=2, seed=17)
allies[0].current_hp = 0
before = list(allies[0].hand)
c.end_player_turn()
report("dead ally keeps its old hand", allies[0].hand == before,
       f"{len(before)} cards retained, never discarded or redrawn")

# --- 8. does combat end if all allies die mid-player-turn? -------------------
c, allies, enemies = fight(seed=19)
allies[0].current_hp = 0
c._check_combat_end()
report("all-allies-dead detected by _check_combat_end", not c.is_over(),
       f"result={c.result}")

print()
print(f"{len(bugs)} finding(s): {bugs}" if bugs else "no findings")

import sys as _sys
_sys.exit(1 if bugs else 0)
