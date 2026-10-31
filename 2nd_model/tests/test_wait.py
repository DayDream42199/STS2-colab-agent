"""Waiting - a player letting the others move first - and the fixed action
menu the agent picks from (Plugins/action_space.py).

The rule (Combat.may_wait): a player may wait while someone else can still
move the turn on - a question to answer, or not yet ended or waiting. The
next play, answer or end turn, by anyone, clears every wait. So of the
players who have not ended, one has always not waited: a round never stalls."""
import json, os, random, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from session import Session, BROADCAST
from combat_log import CombatLog, read, replay
from plugin_host import PluginGuard
from Protocol.protocol import encode
from Protocol.enums import ClientMessage
from GameEngine.Combat.combat import Combat
from GameEngine.Context.context import PendingChoice
from GameEngine.Cards._card_ref import CardRef
from GameEngine.Registry.card_registry import known_card_ids
from GameEngine.Registry.unit_registry import create_ally, create_enemy, register_ally
from GameEngine.Units.Allies._ally import Ally
from Plugins import action_space as menu
from Plugins.aura import create_plugin

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))

WAIT = {"type": "wait"}
END = {"type": "end_turn"}


def fight(n=2, enemies=("dummy1",), seed=1):
    allies = [create_ally("ironclad", "p%d" % (i + 1), rng=random.Random(seed + i)) for i in range(n)]
    foes = [create_enemy(kind, "e%d" % (i + 1), rng=random.Random(seed)) for i, kind in enumerate(enemies)]
    c = Combat(allies, foes, rng=random.Random(seed), scale_enemies=False)
    c.ask_players = True                  # as the session has it
    c.start()
    for foe in foes:
        foe.current_hp = foe.max_hp = 300
    return c, allies, foes


def may(c, ally):
    return WAIT in c.legal_actions(ally)


def refusal(call):
    try:
        call()
    except (ValueError, RuntimeError) as error:
        return str(error)
    return None


def send(s, sid, kind, **payload):
    return s.handle(sid, encode(kind, **payload))


def to(out, kind, sid=None):
    for recipient, m in out:
        if m["type"] == kind and (sid is None or recipient in (sid, BROADCAST)):
            return m["payload"]
    return None


def kinds(out):
    return [m["type"] for _, m in out]


# --- the rule ----------------------------------------------------------------------
print("== who may wait ==")
c, (p,), _ = fight(1)
check("alone: never - nobody else could move the turn on",
      not may(c, p) and refusal(lambda: c.wait(p)) is not None, c.legal_actions(p))

c, (p1, p2), _ = fight(2)
check("two players, neither ended: both may, listed after end turn",
      c.legal_actions(p1)[-2:] == [END, WAIT] and may(c, p2), c.legal_actions(p1)[-2:])
before = json.dumps(c.to_dict(), sort_keys=True, default=str)
c.wait(p1)
after = c.to_dict()
for a in after["allies"]:
    a["waiting"] = False
    a["legal_actions"] = [x for x in a["legal_actions"] if x != WAIT]
before_plain = json.loads(before)
for a in before_plain["allies"]:
    a["legal_actions"] = [x for x in a["legal_actions"] if x != WAIT]
check("p1 waits: nothing in the fight changes but the flag",
      json.loads(json.dumps(after, sort_keys=True, default=str)) == before_plain
      and c.to_dict()["allies"][0]["waiting"] is True)
check("p1 is not offered it again", not may(c, p1))
check("and p2 may not wait as well: someone has to move", not may(c, p2) and END in c.legal_actions(p2))
check("a wait off the list is refused, saying why",
      refusal(lambda: c.wait(p2)) == "Nobody else is still to act: play a card or end your turn.",
      refusal(lambda: c.wait(p2)))

p2.hand, p2.energy = [CardRef("defend")], 3
c.play_card(p2, 0)
check("p2 plays: the wait is cleared and both may wait again",
      not c.waiting and may(c, p1) and may(c, p2), c.waiting)

c.wait(p1)
c.end_turn(p2)
check("p1 waits, p2 ends: p1 decides again, and with nobody else to act may not wait",
      not c.waiting and not may(c, p1) and c.legal_actions(p1)[-1] == END, c.legal_actions(p1)[-2:])
check("an ended player is not offered it either", not may(c, p2))
check("the state says who has ended", [a["ended_turn"] for a in c.to_dict()["allies"]] == [False, True])
p2.hand, p2.energy = [CardRef("defend")], 3
c.play_card(p2, 0)
check("playing after ending takes the end back: p1 may wait on p2 again",
      "p2" not in c.ended_turn and may(c, p1), c.ended_turn)

c, (p1, p2), _ = fight(2)
p2.hand, p2.energy = [CardRef("true_grit", upgraded=True), CardRef("strike"), CardRef("defend")], 3
c.play_card(p2, 0)
check("p2 has a question: only its options, no wait",
      all(a["type"] == "choose" for a in c.legal_actions(p2)), c.legal_actions(p2))
check("refused while it waits", refusal(lambda: c.wait(p2)) == "Answer the choice in front of you first.")
check("p1 may wait on p2's answer", may(c, p1))
c.wait(p1)
c.answer_choice(p2, 0)
check("p2 answers: p1's wait is cleared", not c.waiting and may(c, p1), c.waiting)
c.end_turn(p2)
# A question for a player who has ended - a teammate's card asking them -
# set up by hand: p2 has ended, yet the round cannot end before they answer.
c.pending_choices["p2"] = PendingChoice(ally=p2, prompt="test", options=["strike"],
                                        resolve=lambda chosen: [])
check("a question for a player who has ended still counts: p1 may wait on it", may(c, p1))
del c.pending_choices["p2"]

c, (p1, p2), _ = fight(2)
p2.current_hp = 0
check("a defeated teammate cannot move anything on: no wait", not may(c, p1))
c, (p1, p2), _ = fight(2)
c.wait(p1)
c.forfeit_choices(p2)        # p2 left the session
check("a teammate who left: the wait is cleared, and none is offered",
      not c.waiting and not may(c, p1), (c.waiting, c.legal_actions(p1)[-2:]))

c, (p1, p2, p3), _ = fight(3)
c.wait(p1)
c.wait(p2)
check("three players: two may wait, the third may not",
      not may(c, p3) and c.waiting == {"p1", "p2"}, c.waiting)
c.end_turn(p3)
check("the third ends: both decide again, and may wait on each other",
      not c.waiting and may(c, p1) and may(c, p2))
c.wait(p1)
check("one waits: the other must move", not may(c, p2))

c, (p1, p2), _ = fight(2)
c.wait(p1)
c.end_turn(p2)
c.end_player_turn()
check("a new round: nobody has ended or is waiting",
      not c.ended_turn and not c.waiting and may(c, p1) and may(c, p2))
c, (p1, p2), _ = fight(2)
c.end_turn(p1)
check("p1 ended, p2 not: the round waits (end_player_turn is the session's call)",
      c.phase.name == "PLAYER_TURN" and c.ended_turn == {"p1"})


# --- through the session ----------------------------------------------------------
print("\n== through the session ==")
def table(n=2, seed=1, plugin=None, log=None):
    s = Session(Combat, required_players=n, seed=seed, plugin=plugin, combat_log=log)
    s.ENEMY_TYPE_IDS = ("dummy1",)
    for i in range(n):
        s.add_player("sid%d" % (i + 1))
    for foe in s.combat.enemies:
        foe.current_hp = foe.max_hp = 300
    return s

s = table()
out = send(s, "sid1", ClientMessage.WAIT, decision={"p": 0.7})
check("a wait is answered with who is waiting, to everyone, and no state",
      kinds(out) == ["ready_changed"] and out[0][0] is BROADCAST
      and to(out, "ready_changed") == {"ready": [], "waiting_on": ["p1", "p2"], "waiting": ["p1"]},
      out)
out = send(s, "sid1", ClientMessage.WAIT)
check("waiting twice is refused", kinds(out) == ["error"], out)
out = send(s, "sid2", ClientMessage.END_TURN)
check("p2 ends while p1 waits: the round does not end without p1",
      s.combat.turn_number == 1 and to(out, "ready_changed")["waiting"] == []
      and to(out, "ready_changed")["waiting_on"] == ["p1"], to(out, "ready_changed"))
out = send(s, "sid1", ClientMessage.WAIT)
check("and p1 may not wait on nobody", kinds(out) == ["error"] and "Nobody else" in out[0][1]["payload"]["message"])
send(s, "sid1", ClientMessage.END_TURN)
check("p1 ends: turn 2", s.combat.turn_number == 2 and not s.ready, s.combat.turn_number)

s = table(n=1)
out = send(s, "sid1", ClientMessage.WAIT)
check("alone, a wait is refused", kinds(out) == ["error"], out)

s = table()
s.combat.enemies[0].current_hp = 300
s.players["sid2"].current_hp = 0
out = send(s, "sid2", ClientMessage.WAIT)
check("a defeated player cannot wait", kinds(out) == ["error"] and "defeated" in out[0][1]["payload"]["message"])
out = send(s, "sid1", ClientMessage.WAIT)
check("nor wait on a defeated teammate", kinds(out) == ["error"], out)

s = table()
send(s, "sid1", ClientMessage.WAIT)
out = s.remove_player("sid2")
check("the one waited on leaves: everyone hears who is still to act, the wait cleared",
      to(out, "ready_changed") == {"ready": [], "waiting_on": ["p1"], "waiting": []}, kinds(out))

folder = tempfile.mkdtemp()
s = table(log=CombatLog(folder))
send(s, "sid1", ClientMessage.WAIT, decision={"wait": 0.9})
send(s, "sid1", ClientMessage.WAIT)
lines = read(s.log.path)
wait = next(l for l in lines if l["event"] == "wait")
check("the log has the wait: who, the turn, what was open, the decision",
      wait["unit_id"] == "p1" and wait["turn"] == 1 and WAIT in wait["legal_actions"]
      and wait["decision"] == {"wait": 0.9}, wait)
check("and the refused second one", any(l["event"] == "refused" and l["message"]["type"] == "wait" for l in lines),
      [l["event"] for l in lines])


# --- never stalls; the menu always matches the list --------------------------------
print("\n== random fights: waits never stall a round; the menu matches legal_actions ==")
class WaitProbe(Ally):
    """A player with whatever deck the fight below deals it."""
    DEFAULT_MAX_HP = 90
    DEFAULT_DECK = []
register_ally(WaitProbe)

IDS = [i for i in known_card_ids() if i != "dummy"]
ASKS = ["true_grit", "purity", "armaments", "burning_pact", "headbutt", "wish", "dual_wield",
        "thinking_ahead", "discovery", "seeker_strike", "believe_in_you", "coordinate"]
LINEUPS = [("nibbit",), ("livingfog",), ("twotailedrat", "twotailedrat"),
           ("leafslimemedium", "twigslimesmall"), ("flyconid", "nibbit", "wriggler"),
           ("phrogparasite",), ("kinfollower", "kinfollower", "kinpriest")]

fights, decisions, waits, longest, rounds = 0, 0, 0, {}, 0
refused, mismatched, round_trip, unplaced, extra = [], [], [], {}, []
replays = []
for seed in range(42):
    rng = random.Random(seed)
    WaitProbe.DEFAULT_DECK = [CardRef(rng.choice(IDS), upgraded=rng.random() < 0.3) for _ in range(12)]
    WaitProbe.DEFAULT_DECK += [CardRef(rng.choice(ASKS)) for _ in range(3)]
    players = 2 + seed % 3
    folder = tempfile.mkdtemp()
    s = Session(Combat, required_players=players, seed=seed, combat_log=CombatLog(folder))
    s.ALLY_TYPE_ID = "waitprobe"
    s.ENEMY_TYPE_IDS = LINEUPS[seed % len(LINEUPS)]
    for i in range(players):
        s.add_player("s%d" % i)
    fights += 1
    in_a_row, turn = 0, s.combat.turn_number
    for _step in range(250):
        if not s.is_running():
            break
        open_ = [sid for sid in s.players if s.combat.legal_actions(s.players[sid])
                 and sid not in s.ready]
        open_ = open_ or [sid for sid in s.players if s.combat.legal_actions(s.players[sid])]
        if not open_:
            break
        sid = rng.choice(open_)
        ally = s.players[sid]
        listed = s.combat.legal_actions(ally)
        decisions += 1

        slots = menu.targets(s.combat, ally)
        mask = menu.mask(s.combat, ally, slots)
        placed = set()
        for action in listed:
            index = menu.encode(action, slots)
            if index is None:
                unplaced[action["type"]] = unplaced.get(action["type"], 0) + 1
                continue
            placed.add(index)
            if menu.decode(index, slots) != action:
                round_trip.append((seed, action, index, menu.decode(index, slots)))
        if placed != {i for i, bit in enumerate(mask) if bit}:
            mismatched.append((seed, ally.unit_id, listed))

        # Wait whenever it is open, mostly: the harshest case for stalling.
        if WAIT in listed and rng.random() < 0.9:
            action = WAIT
        else:
            others = [a for a in listed if a not in (END, WAIT)]
            action = rng.choice(others) if others and rng.random() < 0.8 else rng.choice(
                [a for a in listed if a != WAIT])
        out = send(s, sid, ClientMessage(action["type"]),
                   **{k: v for k, v in action.items() if k != "type"})
        if "error" in kinds(out):
            refused.append((seed, ally.unit_id, action, to(out, "error")))
        if action == WAIT:
            waits += 1
            in_a_row += 1
            longest[players] = max(longest.get(players, 0), in_a_row)
        else:
            in_a_row = 0
        if s.is_running() and s.combat.turn_number != turn:
            rounds += 1
            turn = s.combat.turn_number
    replays.append((seed, replay(read(s.log.path), Combat)))

print("%d fights, %d decisions, %d waits, %d rounds; longest run of waits by party size %s; "
      "actions with no menu slot %s" % (fights, decisions, waits, rounds, longest, unplaced))
check("every wait (and every other action) taken from the list was accepted", not refused, refused[:3])
check("waits never ran longer than the other players could answer: fewer in a row than players",
      all(run < size for size, run in longest.items()) and waits > 200, longest)
check("the rounds kept ending", rounds > 100, rounds)
check("the mask is exactly the list laid onto the menu", not mismatched, mismatched[:2])
check("every placed action decodes back to itself", not round_trip, round_trip[:3])
check("nothing but a question's 11th+ option ever lacks a slot",
      set(unplaced) <= {"choose"}, unplaced)
check("a fight with waits in it replays exactly from its log",
      all(not found for _, found in replays), [r for r in replays if r[1]][:2])


# --- the menu itself ----------------------------------------------------------------
print("\n== the menu ==")
check("113 actions: 100 plays, end turn 100, wait 101, options 102-111, stop 112",
      (menu.SIZE, menu.END_TURN, menu.WAIT, menu.CHOOSE, menu.STOP) == (113, 100, 101, 102, 112))
c, (p1, p2), (e1, e2) = fight(2, ("dummy1", "dummy1"))
check("target slots: none, the enemies, then the teammates",
      menu.targets(c, p1) == [None, "e1", "e2", None, None, None, None, "p2", None, None],
      menu.targets(c, p1))
e1.current_hp = 0
p2.current_hp = 0
check("a dead enemy gives up its slot; a defeated teammate keeps theirs",
      menu.targets(c, p1) == [None, "e2", None, None, None, None, None, "p2", None, None],
      menu.targets(c, p1))
p1.hand, p1.energy = [CardRef("defend"), CardRef("strike")], 3
check("Defend in slot 0 (no target), Strike in slot 1 at e2, end turn; nothing else",
      [i for i, bit in enumerate(menu.mask(c, p1)) if bit] == [0, 11, menu.END_TURN],
      [i for i, bit in enumerate(menu.mask(c, p1)) if bit])
check("decode: index -> the message",
      menu.decode(11, menu.targets(c, p1)) == {"type": "play_card", "hand_index": 1, "target_id": "e2"})
check("an option slot maps to the option a divide-and-conquer round fed in",
      menu.decode(menu.CHOOSE + 2, [None] * 10, options=[13, 14, 15])
      == {"type": "choose", "option_index": 15})
check("stop", menu.decode(menu.STOP, [None] * 10) == {"type": "choose", "option_index": -1})

# The agent's format carries it, fresh, with every state and ready_changed.
s = Session(Combat, required_players=2, seed=5, plugin=PluginGuard(create_plugin(), "aura"))
s.ENEMY_TYPE_IDS = ("dummy1",)
s.add_player("sid1")
s.add_player("sid2")
out = send(s, "sid1", ClientMessage.IDENTIFY, role="agent")
state = to(out, "state", "sid1")
p1 = s.players["sid1"]
check("the agent's state: its mask and target slots, as action_space has them",
      state["action_mask"] == menu.mask(s.combat, p1) and state["action_targets"] == menu.targets(s.combat, p1)
      and state["action_mask"][menu.WAIT] == 1)
out = send(s, "sid2", ClientMessage.WAIT)
agent_copy = next(m["payload"] for sid, m in out if sid == "sid1" and m["type"] == "ready_changed")
human_copy = next(m["payload"] for sid, m in out if sid == "sid2" and m["type"] == "ready_changed")
check("a teammate waits: the agent's ready_changed closes its own wait, with no new state",
      agent_copy["action_mask"][menu.WAIT] == 0 and agent_copy["action_mask"][menu.END_TURN] == 1
      and "state" not in kinds(out), agent_copy.get("action_mask", [])[100:102])
check("the human's copy is the player format: no menu", "action_mask" not in human_copy, human_copy)

print()
print("%d checks failed" % len(bad))
for label in bad:
    print("   ", label)

import sys as _sys
_sys.exit(1 if bad else 0)
