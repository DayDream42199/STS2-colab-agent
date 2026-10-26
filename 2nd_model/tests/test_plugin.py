"""The optional server plugin (plugin_host.py): absent, players get the player
format as always; present, it watches the fight through its hooks and shapes
what each client receives - and nothing it does can stop the game."""
import os, random, sys, tempfile, types
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from session import Session, BROADCAST
from plugin_host import load_plugin, NullPlugin, PluginGuard
from Protocol.protocol import encode
from Protocol.enums import ClientMessage, ServerMessage
from GameEngine.Combat.combat import Combat
from GameEngine.Cards._card_ref import CardRef

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))

def kinds(outbound):
    return [m["type"] for _, m in outbound]

def first(outbound, kind, sid="any"):
    """(recipient, payload) of the first message of this kind, optionally to `sid`."""
    for to, m in outbound:
        if m["type"] == kind and (sid == "any" or to == sid):
            return to, m["payload"]
    return None, None

def table(plugin=None, seed=1):
    s = Session(combat_factory=Combat, required_players=2, rng=random.Random(seed), plugin=plugin)
    s.add_player("sid1")
    out = s.add_player("sid2")
    for ally in s.players.values():
        ally.energy = 9
    return s, s.players["sid1"], s.players["sid2"], out

def send(s, sid, kind, **payload):
    return s.handle(sid, encode(kind, **payload))


# --- loading ---------------------------------------------------------------
check("no name: no plugin", isinstance(load_plugin(None), NullPlugin))
check("a name with no file behind it: no plugin, and the game still runs",
      isinstance(load_plugin("Plugins.no_such_plugin_here"), NullPlugin))

broken_dir = tempfile.mkdtemp()
with open(os.path.join(broken_dir, "broken_plugin_for_test.py"), "w") as handle:
    handle.write("import a_dependency_that_is_not_installed\n")
sys.path.insert(0, broken_dir)
check("a plugin file that fails to import: no plugin", isinstance(
    load_plugin("broken_plugin_for_test"), NullPlugin))

empty = types.ModuleType("plugin_without_factory")
sys.modules["plugin_without_factory"] = empty
check("a module without create_plugin(): no plugin",
      isinstance(load_plugin("plugin_without_factory"), NullPlugin))

failing = types.ModuleType("plugin_factory_raises")
failing.create_plugin = lambda: 1 / 0
sys.modules["plugin_factory_raises"] = failing
check("create_plugin() raising: no plugin", isinstance(load_plugin("plugin_factory_raises"), NullPlugin))

good = types.ModuleType("plugin_that_loads")
good.create_plugin = lambda: object()
sys.modules["plugin_that_loads"] = good
loaded = load_plugin("plugin_that_loads")
check("a module with create_plugin(): loaded, behind the guard",
      isinstance(loaded, PluginGuard) and loaded.active, type(loaded).__name__)


# --- no plugin: the player format, broadcasts untouched ---------------------
s, p1, p2, out = table()
check("without a plugin a broadcast stays one broadcast",
      all(to is BROADCAST for to, m in out if m["type"] == "state"), [to for to, _ in out])
p1.hand = [CardRef("bash", upgraded=True)]
out = send(s, "sid1", ClientMessage.PLAY_CARD, hand_index=0, target_id="e1")
to, effects = first(out, "effects")
check("an effects message says which card, on whom (for \"p1 played bash+ on e1\")",
      to is BROADCAST and effects["action"] == "play" and effects["card_id"] == "bash"
      and effects["upgraded"] is True and effects["target_id"] == "e1", effects)

out = send(s, "sid1", ClientMessage.END_TURN)
out = send(s, "sid2", ClientMessage.REQUEST_STATE)
allies = {a["unit_id"]: a for a in first(out, "state")[1]["combat"]["allies"]}
check("the state says who has ended their turn",
      allies["p1"]["ended_turn"] is True and allies["p2"]["ended_turn"] is False,
      {u: a["ended_turn"] for u, a in allies.items()})

out = send(s, "sid1", ClientMessage.IDENTIFY, role="agent")
check("identifying without a plugin: answered with the state, in the player format",
      kinds(out) == ["state"] and out[0][0] == "sid1" and s.roles["sid1"] == "agent", kinds(out))
out = send(s, "sid1", ClientMessage.IDENTIFY, role=7)
check("a role that is not a short string is refused", kinds(out) == ["error"], kinds(out))


# --- a plugin that records the fight and formats for the agent -------------
class Recorder:
    def __init__(self):
        self.log, self.actions, self.seen_states = [], [], []

    def on_identify(self, s, unit_id, role):
        self.log.append(("identify", unit_id, role))

    def on_combat_start(self, s):
        self.log.append(("combat_start",))

    def on_turn_start(self, s):
        self.log.append(("turn_start", s.combat.turn_number))

    def on_action(self, s, action):
        self.log.append(("action", action["action"], action["unit_id"]))
        self.actions.append(action)

    def on_turn_ended(self, s, unit_id):
        ally = next(a for a in s.combat.allies if a.unit_id == unit_id)
        self.log.append(("turn_ended", unit_id, s.combat.turn_number, len(ally.hand)))

    def on_round_end(self, s):
        self.log.append(("round_end", s.combat.turn_number))

    def on_player_left(self, s, unit_id):
        self.log.append(("left", unit_id))

    def on_combat_end(self, s, result):
        self.log.append(("combat_end", result))

    def format_message(self, s, recipient, role, message):
        if message["type"] == "state":
            self.seen_states.append(message)
        if role != "agent":
            return message
        if message["type"] == "ready_changed":
            return None                                   # the agent does not want these
        if message["type"] == "state":
            # Re-laid out, values left in game units: normalizing is the AI's job.
            return {"type": "agent_state", "payload": {
                "turn": s.combat.turn_number,
                "allies": [{"unit_id": a["unit_id"], "hp": a["current_hp"],
                            "ended": a["ended_turn"]} for a in message["payload"]["combat"]["allies"]]}}
        return message

recorder = Recorder()
s, p1, p2, out = table(PluginGuard(recorder))
check("hooks at the start: combat_start, then turn 1 starting",
      recorder.log == [("combat_start",), ("turn_start", 1)], recorder.log)
check("with a plugin a broadcast is split, one copy per player",
      sorted(to for to, m in out if m["type"] == "state") == ["sid1", "sid2"], [to for to, _ in out])

out = send(s, "sid1", ClientMessage.IDENTIFY, role="agent")
check("identify reaches the plugin, and the answer comes in the agent's format",
      recorder.log[-1] == ("identify", "p1", "agent") and kinds(out) == ["agent_state"], kinds(out))

p1.hand = [CardRef("strike"), CardRef("defend")]
out = send(s, "sid1", ClientMessage.PLAY_CARD, hand_index=0, target_id="e1")
action = recorder.actions[-1]
check("on_action: the card as it stood in hand, before the play",
      (action["action"], action["card_id"], action["hand_index"], action["target_id"],
       action["cost"], action["damage"], action["block"], action["energy"])
      == ("play", "strike", 0, "e1", 1, 6, None, 9), action)
check("and what it did", any(r.get("effect_id") == "instant_damage" for r in action["results"]),
      action["results"])
check("the agent gets its format, the human the player format",
      first(out, "agent_state", "sid1")[1] is not None and first(out, "state", "sid2")[1] is not None
      and first(out, "state", "sid1")[1] is None, [(to, m["type"]) for to, m in out])
hp = {a.unit_id: a.current_hp for a in s.combat.allies}
seen = recorder.seen_states[-1]["payload"]["combat"]["allies"]
check("what reaches the plugin is raw: HP in game units, as the engine has it",
      {a["unit_id"]: a["current_hp"] for a in seen} == hp, seen)
check("a copy: the agent's reshaping did not touch the human's message",
      "combat" in first(out, "state", "sid2")[1], first(out, "state", "sid2")[1].keys())

out = send(s, "sid1", ClientMessage.END_TURN)
check("on_turn_ended for p1, in turn 1, with the hand they ended with",
      recorder.log[-1] == ("turn_ended", "p1", 1, 1), recorder.log[-1])
check("a message the plugin holds back (None) is not sent to that player",
      first(out, "ready_changed", "sid1")[1] is None and first(out, "ready_changed", "sid2")[1] is not None,
      [(to, m["type"]) for to, m in out])

p2_hand = len(p2.hand)
out = send(s, "sid2", ClientMessage.END_TURN)
check("the last player's turn end is seen before the round ends, then turn 2 starts",
      recorder.log[-3:] == [("turn_ended", "p2", 1, p2_hand), ("round_end", 1), ("turn_start", 2)],
      recorder.log[-3:])

p1.draw_pile = [CardRef("bash"), CardRef("defend")]
p1.hand = [CardRef("wish")]
send(s, "sid1", ClientMessage.PLAY_CARD, hand_index=0)
out = send(s, "sid1", ClientMessage.CHOOSE, option_index=1)
action = recorder.actions[-1]
check("an answer is its own action: which option, not a play",
      action["action"] == "choose" and action["option_index"] == 1 and action["option"] in ("bash", "defend"),
      action)

s.remove_player("sid2")
check("a player leaving reaches the plugin", ("left", "p2") in recorder.log, recorder.log[-3:])

for e in s.combat.enemies:
    e.current_hp = 1
p1.hand = [CardRef("whirlwind")]
send(s, "sid1", ClientMessage.PLAY_CARD, hand_index=0)
ends = [entry for entry in recorder.log if entry[0] == "combat_end"]
check("on_combat_end, once", ends == [("combat_end", "VICTORY")], ends)


# --- a plugin that raises never stops the game ------------------------------
class Broken:
    def format_message(self, s, recipient, role, message):
        raise RuntimeError("formatting went wrong")

    def on_action(self, s, action):
        raise RuntimeError("the hook went wrong")

s, p1, p2, out = table(PluginGuard(Broken(), "broken"))
check("a format_message that raises: the message goes out in the player format",
      sorted(to for to, m in out if m["type"] == "state") == ["sid1", "sid2"], kinds(out))
p1.hand = [CardRef("strike")]
hp = s.combat.enemies[0].current_hp
out = send(s, "sid1", ClientMessage.PLAY_CARD, hand_index=0, target_id="e1")
check("a hook that raises: the play still happens and is sent",
      s.combat.enemies[0].current_hp < hp and "effects" in kinds(out) and "error" not in kinds(out),
      kinds(out))

print()
print("%d checks failed" % len(bad))
for label in bad:
    print("   ", label)

import sys as _sys
_sys.exit(1 if bad else 0)
