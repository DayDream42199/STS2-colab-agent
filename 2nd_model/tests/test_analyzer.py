"""The Characteristic Analyzer: the spec's arithmetic on turns worked out by
hand (Server/Plugins/analyzer.py), then whole fights through the session with
the agent's plugin gathering the history (Server/Plugins/aura.py)."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from session import Session
from combat_log import CombatLog, read
from plugin_host import PluginGuard
from Protocol.protocol import encode
from Protocol.enums import ClientMessage
from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import register_ally
from GameEngine.Units.Allies._ally import Ally
from Plugins import analyzer
from Plugins.aura import create_plugin

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))

near = lambda a, b: abs(a - b) < 1e-9
STRIKE = {"cost": 1, "dmg": 6, "block": 0, "groups": ["now", "team"]}
DEFEND = {"cost": 1, "dmg": 0, "block": 5, "groups": ["now", "self"]}
INFLAME = {"cost": 1, "dmg": 0, "block": 0, "groups": ["scale", "self"]}
LIFT = {"cost": 1, "dmg": 0, "block": 0, "groups": ["now", "team"]}


def turn(used, opp, energy=3, incoming=10, block=None):
    if block is None:
        block = sum(c["block"] for c in used)        # only their own Block on them
    return {"energy": energy, "used": used, "opp": opp, "incoming": incoming, "block": block}


print("== the arithmetic, by hand ==")
hand = [STRIKE] * 3 + [DEFEND] * 2
found, a, m = analyzer.evidence(turn([STRIKE] * 3, hand))
# A+: 18 damage of a possible 6 per energy x 3 = 100. A-: I = 10, 5 Block per
# energy, so 2 energy was worth blocking with, and none was: 0.
check("three Strikes with 10 coming and two Defends held: A+ 100, A- 0",
      near(m["A+"], 100) and near(m["A-"], 0) and near(a["A-totalcost"], 2), (m["A+"], m["A-"], a["A-totalcost"]))
check("evidence +1 for Aggression, weighted (3 + 2 - 3) / 3",
      near(found["A"]["e"], 1) and near(found["A"]["w"], 2 / 3), found["A"])
check("and +1 for Teamwork: damage is team, Block self",
      near(found["T"]["e"], 1) and near(found["T"]["w"], 2 / 3), found["T"])
check("no Power held: nothing about Scaling", found["S"]["w"] == 0 and found["S"]["e"] == 0, found["S"])

found, a, m = analyzer.evidence(turn([DEFEND, DEFEND, STRIKE], hand))
check("two Defends and a Strike: A+ 33, A- 100 (clipped), evidence -2/3",
      near(m["A+"], 100 / 3) and near(m["A-"], 100) and near(found["A"]["e"], 1 / 3 - 1), (m, found["A"]))

found, _, _ = analyzer.evidence(turn([STRIKE] * 3, hand, energy=5))
check("energy enough for both sides: weight 0, the turn says nothing",
      all(found[t]["w"] == 0 for t in "AST"), found)
found, a, _ = analyzer.evidence(turn([STRIKE] * 3, [STRIKE] * 5))
check("no Block card held: A- total is 0, so no Aggression evidence",
      a["A-totalcost"] == 0 and found["A"]["e"] == 0 and found["A"]["w"] == 0, found["A"])
found, a, _ = analyzer.evidence(turn([STRIKE] * 3, hand, incoming=10, block=10))
check("Block from a teammate covers the hit: I = 0, so nothing to weigh against attacking",
      a["I"] == 0 and a["A-totalcost"] == 0, (a["I"], a["A-totalcost"]))

found, _, m = analyzer.evidence(turn([INFLAME, STRIKE, STRIKE], [INFLAME, STRIKE, STRIKE, STRIKE, STRIKE], incoming=0))
check("Inflame and two Strikes, nothing coming: S+ 100, S- 67, Scaling +1/3",
      near(m["S+"], 100) and near(m["S-"], 2 / 3 * 100) and near(found["S"]["e"], 1 - 2 / 3), (m["S+"], m["S-"], found["S"]))
found, _, m = analyzer.evidence(turn([LIFT, DEFEND, DEFEND], [LIFT, LIFT, LIFT, DEFEND, DEFEND]))
check("a Lift and two Defends: Teamwork leans self (T+ 33, T- 100)",
      near(m["T+"], 100 / 3) and near(m["T-"], 100) and found["T"]["e"] < 0, (m["T+"], m["T-"], found["T"]))

print("\n== the update ==")
p = analyzer.new_profile()
analyzer.update(p, {"A": {"e": 1.0, "w": 2 / 3}, "S": {"e": 0.0, "w": 0.0}, "T": {"e": -0.5, "w": 1.0}})
check("first turn: n = w, so X jumps to e", near(p["A"]["X"], 1) and near(p["T"]["X"], -0.5), p)
check("d takes the surprise, c = (n / beta)(1 - |d| / 2)",
      near(p["A"]["d"], 1) and near(p["A"]["c"], (2 / 3) / analyzer.BETA * 0.5), p["A"])
check("weight 0: untouched", p["S"] == {"X": 0.0, "d": 0.0, "c": 0.0}, p["S"])

p = analyzer.new_profile()
first = None
for i in range(40):
    analyzer.update(p, {"A": {"e": 0.6, "w": 1.0}, "S": {"e": 0, "w": 0}, "T": {"e": 0, "w": 0}})
check("steady evidence: X settles on it, confidence climbs toward 1",
      abs(p["A"]["X"] - 0.6) < 1e-6 and p["A"]["c"] > 0.99, p["A"])
before = p["A"]["X"]
analyzer.update(p, {"A": {"e": -1.0, "w": 1.0}, "S": {"e": 0, "w": 0}, "T": {"e": 0, "w": 0}})
fresh = analyzer.new_profile()
analyzer.update(fresh, {"A": {"e": 0.6, "w": 1.0}, "S": {"e": 0, "w": 0}, "T": {"e": 0, "w": 0}})
analyzer.update(fresh, {"A": {"e": -1.0, "w": 1.0}, "S": {"e": 0, "w": 0}, "T": {"e": 0, "w": 0}})
check("one odd turn barely moves an established profile (and moves a new one a lot)",
      abs(before - p["A"]["X"]) < abs(0.6 - fresh["A"]["X"]) and abs(before - p["A"]["X"]) < 0.25,
      (before - p["A"]["X"], 0.6 - fresh["A"]["X"]))
check("CV is A, S, T and their confidences", sorted(analyzer.values(p)) == ["A", "S", "T", "cA", "cS", "cT"])

print("\n== through the session ==")
class FiveCards(Ally):
    """Draws its whole deck: the opening hand is exactly this."""
    DEFAULT_MAX_HP = 80
    DEFAULT_DECK = ["strike", "strike", "strike", "defend", "defend"]
register_ally(FiveCards)


def fight(plays_by_p2, turns=1):
    folder = tempfile.mkdtemp()
    s = Session(Combat, required_players=2, seed=4, combat_log=CombatLog(folder),
                plugin=PluginGuard(create_plugin(), "aura"))
    s.ALLY_TYPE_ID = "fivecards"
    s.ENEMY_TYPE_IDS = ("dummy1", "dummy1")
    s.add_player("bot")
    s.handle("bot", encode(ClientMessage.IDENTIFY, role="agent"))
    s.add_player("human")
    outs = []
    for _ in range(turns):
        for e in s.combat.enemies:
            e.current_hp = e.max_hp = 500
            e.intent = {"type": "attack", "amount": 5, "hits": 1}      # 5 + 5 at each player
        p2 = s.players["human"]
        for card_id in plays_by_p2:
            index = next(i for i, c in enumerate(p2.hand) if str(c) == card_id)
            target = "e1" if card_id == "strike" else None
            s.handle("human", encode(ClientMessage.PLAY_CARD, hand_index=index, target_id=target))
        s.handle("human", encode(ClientMessage.END_TURN))
        outs.append(s.handle("bot", encode(ClientMessage.END_TURN)))
    global last_log
    last_log = os.path.join(folder, os.listdir(folder)[0])
    lines = read(last_log)
    return s, outs, [l for l in lines if l["event"] == "profile_update"]


def inputs():
    return [l for l in read(last_log) if l["event"] == "analyzer_input"]


s, outs, updates = fight(["strike", "strike", "strike"])
check("one profile update, for the teammate (p2) only, not the agent",
      [u["unit_id"] for u in updates] == ["p2"], [u["unit_id"] for u in updates])
u = updates[0]
given = inputs()
check("the analyzer's input is logged too, once per scored turn, for p2",
      [x["unit_id"] for x in given] == ["p2"] and given[0]["seq"] < u["seq"], [x["unit_id"] for x in given])
h = given[0]
check("the spec's History: 3 energy, 5 cards in Opp, 3 Used, 2 left in Hand, 10 coming, 0 Block",
      h["energy"] == 3 and len(h["opp"]) == 5 and len(h["used"]) == 3 and len(h["hand"]) == 2
      and h["incoming"] == 10 and h["block"] == 0, {k: h[k] for k in ("energy", "incoming", "block")})
check("each card says which it is and what it was worth: a Strike 1 energy, 6 damage, team",
      h["used"][0] == {"id": "strike", "upgraded": False, "cost": 1, "dmg": 6, "block": 0,
                       "groups": ["now", "team"]}
      and sorted(c["id"] for c in h["hand"]) == ["defend", "defend"], (h["used"][0], h["hand"]))
found, _, _ = analyzer.evidence(h)
check("fed back to the analyzer, the logged input gives the logged evidence",
      found == u["evidence"], (found, u["evidence"]))
check("three Strikes while 10 was coming: Aggression +1", near(u["profile"]["A"], 1), u["profile"])
agent_state = next(m for to, m in outs[0] if to == "bot" and m["type"] == "state")
human_state = next(m for to, m in outs[0] if to == "human" and m["type"] == "state")
check("the agent's state carries p2's profile, the human's carries none",
      "p2" in agent_state["payload"].get("profiles", {}) and "profiles" not in human_state["payload"],
      agent_state["payload"].get("profiles"))

s, outs, updates = fight(["defend", "defend", "strike"])
check("two Defends and a Strike: Aggression below 0", updates and updates[0]["profile"]["A"] < 0,
      updates and updates[0]["profile"])

s, outs, updates = fight(["strike", "strike", "strike"], turns=3)
check("three turns, three updates, confidence growing",
      len(updates) == 3 and updates[0]["profile"]["cA"] < updates[1]["profile"]["cA"] < updates[2]["profile"]["cA"],
      [round(x["profile"]["cA"], 3) for x in updates])

print("\n== the input, exported for the MockUpRB prototype ==")
from Plugins import history_export
out_dir = tempfile.mkdtemp()
written = history_export.export(last_log, out_dir)
check("one file per teammate: p2's three turns",
      [(os.path.basename(p).endswith("_p2.json"), n) for p, n in written] == [(True, 3)], written)
turns = json.load(open(written[0][0], encoding="utf-8"))
first = turns[0]
check("each turn is [E_total, Used, Opp, D, B], each card [cost, dmg, block, groups]",
      len(first) == 5 and first[0] == 3 and first[3] == 10 and first[4] == 0
      and first[1][0] == [1, 6, 0, ["now", "team"]] and len(first[2]) == 5, first[:1] + first[3:])
import subprocess
result = subprocess.run([sys.executable, "-m", "Plugins.history_export", last_log, out_dir],
                        cwd=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"),
                        capture_output=True, text=True)
check("python -m Plugins.history_export <log> works from Server/",
      result.returncode == 0 and "3 turns" in result.stdout, result.stdout + result.stderr)

print("\n== random fights: it never breaks, and every number stays in range ==")
import random
from GameEngine.Registry.card_registry import known_card_ids
from GameEngine.Cards._card_ref import CardRef

class Probe(Ally):
    DEFAULT_MAX_HP = 60
    DEFAULT_DECK = []
register_ally(Probe)
ids, seen, out_of_range, errors, logs = list(known_card_ids()), 0, [], 0, []
for seed in range(15):
    rng = random.Random(seed)
    Probe.DEFAULT_DECK = [CardRef(rng.choice(ids), upgraded=rng.random() < 0.3) for _ in range(14)]
    folder = tempfile.mkdtemp()
    s = Session(Combat, required_players=2 + seed % 2, seed=seed, combat_log=CombatLog(folder),
                plugin=PluginGuard(create_plugin(), "aura"))
    s.ALLY_TYPE_ID = "probe"
    s.ENEMY_TYPE_IDS = (("nibbit",), ("leafslimemedium", "twigslimesmall"), ("flyconid", "wriggler"))[seed % 3]
    for i in range(s.required_players):
        s.add_player("s%d" % i)
    s.handle("s0", encode(ClientMessage.IDENTIFY, role="agent"))
    for step in range(150):
        if not s.is_running():
            break
        if step == 60 and s.required_players == 3:
            s.remove_player("s2")                          # a player leaving mid-fight
        sids = ([sid for sid in s.players if s.combat.legal_actions(s.players[sid]) and sid not in s.ready]
                or [sid for sid in s.players if s.combat.legal_actions(s.players[sid])])
        if not sids:
            break
        sid = rng.choice(sids)
        acts = s.combat.legal_actions(s.players[sid])
        plays = [a for a in acts if a["type"] != "end_turn"]
        a = rng.choice(plays) if plays and rng.random() < 0.8 else rng.choice(acts)
        s.handle(sid, encode(ClientMessage(a["type"]), **{k: v for k, v in a.items() if k != "type"}))
    logs.append(os.path.join(folder, os.listdir(folder)[0]))
    for line in read(logs[-1]):
        errors += line["event"] == "error"
        if line["event"] != "profile_update":
            continue
        seen += 1
        p, ev = line["profile"], line["evidence"]
        if not (all(-1 <= p[t] <= 1 and 0 <= p["c" + t] <= 1 for t in "AST")
                and all(-1 <= ev[t]["e"] <= 1 and 0 <= ev[t]["w"] <= 1 for t in "AST")):
            out_of_range.append(line)
check("random decks, questions, deaths, a player leaving: no errors, plenty of updates",
      errors == 0 and seen > 30, (errors, seen))
check("every e in [-1, 1], w in [0, 1], X in [-1, 1], c in [0, 1]", not out_of_range, out_of_range[:1])

# The teammate's package (2nd_model/CharacteristicAnalyzer), fed the same turns from the logs.
from Plugins import ca_feed
if os.path.isdir(ca_feed.PACKAGE):
    gaps, turns = [], 0
    for log in logs:
        found, _ = ca_feed.feed(log, tempfile.mkdtemp())
        for rows in found.values():
            turns += len(rows)
            gaps += [abs(theirs[k] - ours[k]) for _, theirs, ours, _ in rows for k in ca_feed.KEYS]
    check("CharacteristicAnalyzer gives our numbers at its own beta, turn for turn",
          turns > 30 and max(gaps) < 1e-9, (turns, max(gaps)))

    # Its charts: the page carries every player's turns and says they agree.
    from Plugins import ca_plot
    found, beta = ca_feed.feed(logs[0], tempfile.mkdtemp())
    data = ca_plot.chart_data(found, beta)
    page = os.path.join(tempfile.mkdtemp(), "ca.html")
    ca_plot.write_html(data, "test </script>", page)
    text = open(page, encoding="utf-8").read()
    check("ca_plot draws every player's turns, with all six numbers each",
          [p["id"] for p in data["players"]] == list(found)
          and all(len(p["turns"]) == len(found[p["id"]]) and set(ca_feed.KEYS) <= set(p["turns"][0])
                  for p in data["players"]), [p["id"] for p in data["players"]])
    check("and the page holds that data and says the two analyzers agree",
          data["agree"] and json.dumps(data["players"][0]["turns"][0]) in text
          and "test &lt;/script&gt;" in text, data["gap"])
else:
    print("[SKIP] CharacteristicAnalyzer is not here: nothing to compare with")

print()
print("%d checks failed" % len(bad))
for label in bad:
    print("   ", label)

import sys as _sys
_sys.exit(1 if bad else 0)
