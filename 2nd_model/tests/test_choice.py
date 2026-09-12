"""Player choice, end to end through Session: ask, wait, answer, finish."""
import json, random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from session import Session, BROADCAST
from Protocol.protocol import encode
from Protocol.enums import ClientMessage, ServerMessage
from GameEngine.Combat.combat import Combat
from GameEngine.Cards._card_ref import CardRef, is_upgraded

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))

def hand(*ids):
    return [CardRef(i) for i in ids]

def kinds(outbound):
    return [m["type"] for _, m in outbound]

def to(outbound, kind):
    """(recipient, payload) for the first message of this kind."""
    for sid, m in outbound:
        if m["type"] == kind:
            return sid, m["payload"]
    return None, None

def table(seed=1):
    s = Session(combat_factory=Combat, required_players=2, rng=random.Random(seed))
    s.add_player("sid1")
    s.add_player("sid2")
    for ally in s.players.values():
        ally.energy = 9
    return s, s.players["sid1"], s.players["sid2"]

def play(s, sid, index=0, target=None):
    return s.handle(sid, encode(ClientMessage.PLAY_CARD,
                                hand_index=index, target_id=target))

def choose(s, sid, index):
    return s.handle(sid, encode(ClientMessage.CHOOSE, option_index=index))


# --- a card that asks -------------------------------------------------------
s, p1, p2 = table()
p1.hand = hand("wish")
p1.draw_pile = hand("bash", "defend", "strike")
out = play(s, "sid1")
check("playing Wish asks a question instead of resolving",
      ServerMessage.CHOICE_REQUIRED.value in kinds(out), kinds(out))

sid, ask = to(out, ServerMessage.CHOICE_REQUIRED.value)
check("the question goes only to the player who has to answer", sid == "sid1", sid)
check("it names who, why, and what the options are",
      ask["unit_id"] == "p1" and ask["prompt"] and len(ask["options"]) == 3,
      ask)
check("the options are plain strings, ready for the wire",
      all(isinstance(o, str) for o in ask["options"]), ask["options"])
check("nothing has moved yet",
      len(p1.hand) == 0 and len(p1.draw_pile) == 3,
      (p1.hand, p1.draw_pile))
check("and the state broadcast carries it too",
      to(out, ServerMessage.STATE.value)[1]["combat"]["choices"].get("p1") is not None)

wanted = ask["options"][1]
out = choose(s, "sid1", 1)
check("answering moves the card the player actually picked",
      p1.hand == [wanted] and len(p1.draw_pile) == 2, (p1.hand, p1.draw_pile))
check("and the question is gone", not s.combat.pending_choices,
      s.combat.pending_choices)
check("the answer is broadcast as effects",
      ServerMessage.EFFECTS.value in kinds(out), kinds(out))

# --- the guards -------------------------------------------------------------
s, p1, p2 = table()
p1.hand = hand("wish", "strike")
p1.draw_pile = hand("bash", "defend")
play(s, "sid1")
out = play(s, "sid1", 0, "e1")
check("you cannot play another card while a question is open",
      ServerMessage.ERROR.value in kinds(out), kinds(out))

out = s.handle("sid1", encode(ClientMessage.END_TURN))
check("nor end your turn", ServerMessage.ERROR.value in kinds(out),
      to(out, ServerMessage.ERROR.value)[1])

out = choose(s, "sid1", 99)
check("an out-of-range answer is refused", ServerMessage.ERROR.value in kinds(out),
      to(out, ServerMessage.ERROR.value)[1])
check("and the question is still open", "p1" in s.combat.pending_choices)

out = choose(s, "sid2", 0)
check("the other player cannot answer it for you",
      ServerMessage.ERROR.value in kinds(out),
      to(out, ServerMessage.ERROR.value)[1])

# --- the other player is not blocked ----------------------------------------
s, p1, p2 = table()
p1.hand = hand("wish")
p1.draw_pile = hand("bash", "defend")
p2.hand = hand("strike")
play(s, "sid1")
enemy_hp = s.combat.enemies[0].current_hp
out = play(s, "sid2", 0, "e1")
check("p2 can still act while p1 is choosing",
      s.combat.enemies[0].current_hp < enemy_hp
      and ServerMessage.ERROR.value not in kinds(out), kinds(out))

# --- a turn cannot advance on an unanswered question ------------------------
s, p1, p2 = table()
p1.hand = hand("wish")
p1.draw_pile = hand("bash", "defend")
p2.hand = hand("strike")
play(s, "sid1")
s.handle("sid2", encode(ClientMessage.END_TURN))
turn_before = s.combat.phase.name
check("both ready is not enough while a question is open",
      turn_before == "PLAYER_TURN" and "p1" in s.combat.pending_choices)
out = choose(s, "sid1", 0)
check("answering it lets the turn advance",
      ServerMessage.STATE.value in kinds(out), kinds(out))

# --- multi-pick asks one at a time ------------------------------------------
s, p1, p2 = table()
p1.hand = hand("purity", "strike", "defend", "bash")
out = play(s, "sid1")
_, ask = to(out, ServerMessage.CHOICE_REQUIRED.value)
check("Purity asks for the first of three", "3 left" in ask["prompt"], ask["prompt"])
check("and offers the whole hand", len(ask["options"]) == 3, ask["options"])
first = ask["options"][0]
out = choose(s, "sid1", 0)
_, ask = to(out, ServerMessage.CHOICE_REQUIRED.value)
check("then asks again over what is left",
      ask is not None and "2 left" in ask["prompt"] and first not in ask["options"],
      ask)
check("and the first pick is already exhausted",
      p1.exhaust_pile == ["purity", first],   # Purity exhausts itself too
      p1.exhaust_pile)
choose(s, "sid1", 0)
out = choose(s, "sid1", 0)
check("three answers exhaust three cards and end the questions",
      len(p1.exhaust_pile) == 4 and not s.combat.pending_choices,
      (p1.exhaust_pile, s.combat.pending_choices))

# --- two questions for one player, and one for the other ----------------------
from GameEngine.Effects.StatusEffects.entropy import Entropy
from GameEngine.Effects.StatusEffects.stratagem import Stratagem

def pin(s):
    for e in s.combat.enemies:
        e.choose_intent = lambda context=None, e=e: setattr(
            e, "intent", {"type": "attack", "amount": 1})
        e.choose_intent()

s, p1, p2 = table()
pin(s)
p1.apply_status(Entropy(source=p1, target=p1, amount=1))
p1.apply_status(Stratagem(source=p1, target=p1, amount=1))
p1.hand, p1.draw_pile = [], []
p1.discard_pile = hand("strike", "strike", "strike", "strike", "strike", "strike")
p2.hand = hand("strike")
s.handle("sid1", encode(ClientMessage.END_TURN))
s.handle("sid2", encode(ClientMessage.END_TURN))
first = s.combat.pending_choices.get("p1")
check("turn start parks one of p1's two questions and queues the other",
      first is not None and len(s.combat._asks) == 1,
      (first.prompt if first else None, [a.prompt for a in s.combat._asks]))

p2.hand = hand("wish")
p2.draw_pile = hand("bash")
play(s, "sid2")
check("p2 asking does not overwrite p1's parked question",
      s.combat.pending_choices.get("p1") is first,
      s.combat.pending_choices.get("p1").prompt)
check("and p2 gets their own slot at the same time",
      s.combat.pending_choices.get("p2") is not None,
      list(s.combat.pending_choices))

choose(s, "sid1", 0)
second = s.combat.pending_choices.get("p1")
check("answering p1's first puts up p1's second, in order",
      second is not None and second is not first, second.prompt if second else None)
choose(s, "sid1", 0)
choose(s, "sid2", 0)
check("three answers clear every question", not s.combat.pending_choices
      and not s.combat._asks, (s.combat.pending_choices, s.combat._asks))

# --- a player leaves mid-question -------------------------------------------
s, p1, p2 = table()
p1.hand = hand("wish")
p1.draw_pile = hand("bash", "defend")
p2.hand = hand("strike")
play(s, "sid1")
check("p1 is being asked", "p1" in s.combat.pending_choices)
out = s.remove_player("sid1")
check("when p1 leaves, their question answers itself",
      "p1" not in s.combat.pending_choices and len(p1.hand) == 1,
      (list(s.combat.pending_choices), p1.hand))
check("and the outcome is broadcast so p2 sees it",
      ServerMessage.EFFECTS.value in kinds(out), kinds(out))
s.handle("sid2", encode(ClientMessage.END_TURN))
check("the turn can advance without them",
      s.combat.phase.name == "PLAYER_TURN" and p2.energy == 3, (s.combat.phase.name, p2.energy))

s, p1, p2 = table()
p1.apply_status(Entropy(source=p1, target=p1, amount=1))
p1.hand = hand("strike", "defend")
s.remove_player("sid1")
pin(s)
p2.hand = hand("strike")
s.handle("sid2", encode(ClientMessage.END_TURN))
check("and a question raised for them later answers itself too",
      not s.combat.pending_choices and s.combat.phase.name == "PLAYER_TURN",
      (list(s.combat.pending_choices), s.combat.phase.name))

# --- headless still plays itself --------------------------------------------
allies = [__import__("GameEngine.Registry.unit_registry", fromlist=["x"])
          .create_ally("testally1", "p1", rng=random.Random(2))]
enemies = [__import__("GameEngine.Registry.unit_registry", fromlist=["x"])
           .create_enemy("dummy1", "e1", rng=random.Random(2))]
c = Combat(allies, enemies, rng=random.Random(2))
c.start()
allies[0].energy = 9
allies[0].hand = hand("wish")
allies[0].draw_pile = hand("bash", "defend")
c.play_card(allies[0], 0)
check("with nobody to ask, the card answers itself and does not stall",
      len(allies[0].hand) == 1 and not c.pending_choices,
      (allies[0].hand, c.pending_choices))

print()
print("%d checks failed" % len(bad))
for label in bad:
    print("   ", label)

import sys as _sys
_sys.exit(1 if bad else 0)
