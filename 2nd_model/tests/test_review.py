"""Drive the real Combat through Session. No sockets."""
import json
import random
import sys

import os
SERVER = os.path.join(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."), "Server")
sys.path.insert(0, SERVER)

from session import Session
from Protocol.enums import ClientMessage, ServerMessage
from Protocol.protocol import encode
from GameEngine.Combat.combat import Combat, CombatPhase, CombatResult
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Registry.card_registry import create_card
from GameEngine.Effects.StatusEffects.vulnerable import Vulnerable
from GameEngine.Resolution.resolver import Resolver

notes = []

def check(label, cond, detail=""):
    if not cond:
        notes.append(label)
    print(f"[{'PASS' if cond else 'FAIL'}] {label}{(' -> ' + str(detail)) if detail else ''}")

def find(out, mt):
    for _, m in out:
        if m["type"] == mt.value:
            return m["payload"]
    return None


# --- Session + real Combat ---------------------------------------------------
s = Session(combat_factory=Combat, required_players=1, rng=random.Random(7))
out = s.add_player("s1")
check("session starts real combat", s.is_running())
check("welcome + state", find(out, ServerMessage.WELCOME) and find(out, ServerMessage.STATE))
st = find(out, ServerMessage.STATE)["combat"]
check("state JSON-serializable", isinstance(json.dumps(st), str))
check("phase PLAYER_TURN", st["phase"] == "PLAYER_TURN", st["phase"])
check("hand of 5", len(st["allies"][0]["hand"]) == 5, st["allies"][0]["hand"])
check("enemy intent present", st["enemies"][0]["intent"] is not None)
print("    contract keys:", sorted(st.keys()))

ally = s.ally_for("s1")
enemy = s.combat.enemies[0]

# --- play a real card over the protocol --------------------------------------
ally.hand = ["strike"]
enemy.current_hp = enemy.max_hp = 40
out = s.handle("s1", encode(ClientMessage.PLAY_CARD, hand_index=0, target_id=enemy.unit_id))
eff = find(out, ServerMessage.EFFECTS)
check("strike deals 6", enemy.current_hp == 34, enemy.current_hp)
check("effects payload shape", eff and eff["results"][0]["amount"] == 6, eff)

# --- vulnerable math ---------------------------------------------------------
ally.hand = ["bash", "strike"]
ally.energy = 3
enemy.current_hp = enemy.max_hp = 60
s.handle("s1", encode(ClientMessage.PLAY_CARD, hand_index=0, target_id=enemy.unit_id))
check("bash deals 8", enemy.current_hp == 52, enemy.current_hp)
check("bash applies vulnerable 2", enemy.get_status("vulnerable").amount == 2)
s.handle("s1", encode(ClientMessage.PLAY_CARD, hand_index=0, target_id=enemy.unit_id))
check("strike into vulnerable deals 9", enemy.current_hp == 43, enemy.current_hp)

# --- rounding: STS floors, this rounds ---------------------------------------
class Five:
    def __init__(self): self.statuses = {}; self.unit_id = "x"
src0 = create_ally("testally1", "src0", rng=random.Random(1))
target = create_enemy("dummy1", "t1", rng=random.Random(1))
target.current_hp = target.max_hp = 100
target.apply_status(Vulnerable(source=src0, target=target, amount=3))
from GameEngine.Effects.InstantEffects.instant_damage import InstantDamage
src = create_ally("testally1", "src", rng=random.Random(1))
r = Resolver.resolve(InstantDamage(source=src, target=target, amount=5))
check("5 dmg + vulnerable floors to 7", r["amount"] == 7, f"got {r['amount']}")

# --- status instance aliasing ------------------------------------------------
a1 = create_ally("testally1", "a1", rng=random.Random(1))
a2 = create_ally("testally1", "a2", rng=random.Random(1))
shared = Vulnerable(source=a1, target=a1, amount=2)
Resolver.resolve(shared)
shared.target = a2
Resolver.resolve(shared)
same = a1.get_status("vulnerable") is a2.get_status("vulnerable")
check("statuses are per-target copies", not same,
      f"a1={a1.get_status('vulnerable').amount} a2={a2.get_status('vulnerable').amount}")

# --- turn cycle --------------------------------------------------------------
s2 = Session(combat_factory=Combat, required_players=1, rng=random.Random(11))
s2.add_player("s1")
a = s2.ally_for("s1")
hp_before = a.current_hp
out = s2.handle("s1", encode(ClientMessage.END_TURN))
st = find(out, ServerMessage.STATE)["combat"]
check("turn cycles back to PLAYER_TURN", st["phase"] == "PLAYER_TURN", st["phase"])
check("energy refreshed", st["allies"][0]["energy"] == 3, st["allies"][0]["energy"])
check("redrew to 5", len(st["allies"][0]["hand"]) == 5, len(st["allies"][0]["hand"]))
check("no 'turn' key in to_dict", "turn" not in st, sorted(st.keys()))

# --- hand cap ----------------------------------------------------------------
s3 = Session(combat_factory=Combat, required_players=1, rng=random.Random(13))
s3.add_player("s1")
a3 = s3.ally_for("s1")
for _ in range(4):
    if s3.is_running():
        s3.handle("s1", encode(ClientMessage.END_TURN))
check("hand can exceed 10 (no cap)", len(a3.hand) <= 10,
      f"hand={len(a3.hand)} after 4 turns of drawing 5 without discard-limit")

# --- victory -----------------------------------------------------------------
s4 = Session(combat_factory=Combat, required_players=1, rng=random.Random(17))
s4.add_player("s1")
e4 = s4.combat.enemies[0]
e4.current_hp = 1
s4.ally_for("s1").hand = ["strike"]
out = s4.handle("s1", encode(ClientMessage.PLAY_CARD, hand_index=0, target_id=e4.unit_id))
check("combat_ended broadcast", find(out, ServerMessage.COMBAT_ENDED) is not None,
      [m["type"] for _, m in out])
check("result VICTORY", find(out, ServerMessage.COMBAT_ENDED)["result"] == "VICTORY")

# --- two-player co-op --------------------------------------------------------
duo = Session(combat_factory=Combat, required_players=2, rng=random.Random(19))
duo.add_player("a"); duo.add_player("b")
check("2p combat starts", duo.is_running())
check("two allies in combat", len(duo.combat.allies) == 2)
out = duo.handle("a", encode(ClientMessage.END_TURN))
check("waits on p2", find(out, ServerMessage.READY_CHANGED)["waiting_on"] == ["p2"])
duo.handle("b", encode(ClientMessage.END_TURN))
check("advances when both ready", duo.combat.phase is CombatPhase.PLAYER_TURN)

print()
print(f"{len(notes)} note(s): {notes}" if notes else "all clean")

import sys as _sys
_sys.exit(1 if notes else 0)
