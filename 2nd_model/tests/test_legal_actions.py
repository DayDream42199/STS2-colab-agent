"""Combat.legal_actions: at every decision point, the actions a player may send.

The promise is two-sided - every action listed is accepted, and every action
not listed is refused - so the fights below try both, through the real Session,
each on a copy so the fight itself goes on untouched."""
import copy, json, random, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Server"))

from session import Session
from Protocol.protocol import encode, decode
from Protocol.enums import ClientMessage, ServerMessage
from GameEngine.Combat.combat import Combat, CombatPhase
from GameEngine.Context.context import PendingChoice
from GameEngine.Registry.card_registry import create_card, known_card_ids
from GameEngine.Registry.unit_registry import create_ally, create_enemy, register_ally
from GameEngine.Cards._card_enums import TargetType
from GameEngine.Cards._card_ref import CardRef
from GameEngine.Units.Allies._ally import Ally

bad = []
def check(l, c, d=""):
    if not c: bad.append(l)
    print("[%s] %s%s" % ("PASS" if c else "FAIL", l, (" -> " + str(d)) if d else ""))


def fight(n_allies=1, n_enemies=1, seed=1):
    allies = [create_ally("ironclad", "p%d" % (i + 1), rng=random.Random(seed + i))
              for i in range(n_allies)]
    enemies = [create_enemy("dummy1", "e%d" % (i + 1), rng=random.Random(seed))
               for i in range(n_enemies)]
    c = Combat(allies, enemies, rng=random.Random(seed), scale_enemies=False)
    c.ask_players = True                  # as the session has it: questions wait for an answer
    c.start()
    for e in enemies:
        e.current_hp = e.max_hp = 300
    return c, allies, enemies


def plays(actions):
    return sorted((a["hand_index"], a["target_id"] or "") for a in actions if a["type"] == "play_card")


# --- the rules, one at a time ------------------------------------------------------
print("== what is listed ==")
c, (p,), (e1, e2) = fight(n_enemies=2)
p.hand, p.energy = [CardRef("strike"), CardRef("defend"), CardRef("bash")], 3
check("Strike at each enemy, Defend once, Bash at each, and end turn",
      c.legal_actions(p) == [
          {"type": "play_card", "hand_index": 0, "target_id": "e1"},
          {"type": "play_card", "hand_index": 0, "target_id": "e2"},
          {"type": "play_card", "hand_index": 1, "target_id": None},
          {"type": "play_card", "hand_index": 2, "target_id": "e1"},
          {"type": "play_card", "hand_index": 2, "target_id": "e2"},
          {"type": "end_turn"}], c.legal_actions(p))

e2.current_hp = 0
check("a dead enemy is no target", plays(c.legal_actions(p)) == [(0, "e1"), (1, ""), (2, "e1")],
      plays(c.legal_actions(p)))

p.energy = 1
check("1 energy: Bash (2) is not on the list", plays(c.legal_actions(p)) == [(0, "e1"), (1, "")],
      plays(c.legal_actions(p)))
p.energy = 0
check("no energy: only end turn", c.legal_actions(p) == [{"type": "end_turn"}], c.legal_actions(p))
p.free_this_turn.append("bash")
check("a free Bash is playable at 0 energy", plays(c.legal_actions(p)) == [(2, "e1")],
      plays(c.legal_actions(p)))

c, (p,), _ = fight()
p.hand, p.energy = [CardRef("strike"), CardRef("burn"), CardRef("clash")], 3
check("an Unplayable card is left out; Clash, with a Status held, too",
      plays(c.legal_actions(p)) == [(0, "e1")], plays(c.legal_actions(p)))
p.hand, p.energy = [CardRef("whirlwind"), CardRef("sword_boomerang")], 3
check("an X-cost card and a random-target card: one action each, target None",
      plays(c.legal_actions(p)) == [(0, ""), (1, "")], plays(c.legal_actions(p)))

c, (p,), _ = fight()
p.hand, p.energy = [CardRef("strike"), CardRef("enthralled"), CardRef("enthralled")], 3
listed = plays(c.legal_actions(p))
check("Enthralled held: it is the only play, and only its first copy", listed == [(1, "")], listed)
p.hand = [CardRef("strike"), CardRef("strike"), CardRef("normality")]
p.turn_counters["cards_played"] = 3
check("Normality after 3 plays: no play is open, end turn still is",
      c.legal_actions(p) == [{"type": "end_turn"}], c.legal_actions(p))

c, (p, q), _ = fight(n_allies=2)
p.hand, p.energy = [CardRef("believe_in_you")], 3
check("a card for another player: the teammate, never yourself",
      plays(c.legal_actions(p)) == [(0, "p2")], plays(c.legal_actions(p)))
q.current_hp = 0
check("a defeated teammate cannot be picked", plays(c.legal_actions(p)) == [], plays(c.legal_actions(p)))
check("a defeated player has nothing to do", c.legal_actions(q) == [], c.legal_actions(q))
c, (p,), _ = fight()
p.hand, p.energy = [CardRef("believe_in_you")], 3
check("alone, a card for another player has no target", plays(c.legal_actions(p)) == [],
      plays(c.legal_actions(p)))

c, (p,), _ = fight()
p.hand, p.energy = [CardRef("true_grit", upgraded=True), CardRef("strike"), CardRef("defend")], 3
c.play_card(p, 0)
ask = c.choice_for(p)
check("a question waiting: only its options, no play and no end turn",
      c.legal_actions(p) == [{"type": "choose", "option_index": i} for i in range(len(ask.options))],
      c.legal_actions(p))
c, (p,), _ = fight()
p.hand, p.energy = [CardRef("purity"), CardRef("strike"), CardRef("defend")], 3
c.play_card(p, 0)
check("an \"up to N\" question also lists stopping (-1)",
      {"type": "choose", "option_index": PendingChoice.STOP} in c.legal_actions(p), c.legal_actions(p))

c, (p,), _ = fight()
c.phase = CombatPhase.ENEMY_TURN
check("outside the player turn: nothing", c.legal_actions(p) == [], c.legal_actions(p))
c.phase = CombatPhase.PLAYER_TURN
check("the state carries each player's list", c.to_dict()["allies"][0]["legal_actions"] == c.legal_actions(p))

# Nothing is rolled: listing a random-target card leaves the stream where it was.
c, (p,), _ = fight()
p.hand, p.energy = [CardRef("sword_boomerang")], 3
states = lambda: [getattr(c.rngs, name).getstate() for name in c.rngs.NAMES]
before = states()
c.legal_actions(p)
check("listing draws nothing from any random stream", states() == before)


# --- both ways, through the session, in random fights -------------------------------------
print("\n== listed is accepted, unlisted is refused ==")
class LegalProbe(Ally):
    """A player with whatever deck the fight below deals it."""
    DEFAULT_MAX_HP = 90
    DEFAULT_DECK = []
register_ally(LegalProbe)

PLAYABLE_IDS = [i for i in known_card_ids() if i not in ("dummy",)]
# Rare in a random deck, so each deck is dealt one of each.
FOR_A_TEAMMATE = [i for i in PLAYABLE_IDS if create_card(i).target_type is TargetType.ALLY]
ASKS = ["true_grit", "purity", "armaments", "burning_pact", "headbutt", "wish", "dual_wield",
        "thinking_ahead", "discovery", "seeker_strike"]
FAKE = "x9"     # a unit nobody is


def refused(outbound, sid):
    """True if the sender got an error back - "crash" if it was not a refusal
    but an unexpected error the session caught."""
    for to, raw in outbound:
        if to == sid:
            kind, payload = decode(raw, ServerMessage)
            if kind is ServerMessage.ERROR:
                return "crash" if "unexpected error" in payload["message"] else True
    return False


def as_message(action):
    payload = {k: v for k, v in action.items() if k != "type"}
    return encode(ClientMessage(action["type"]), **payload)


def candidates(s, ally):
    """Every action worth trying: each hand index around the hand, at every
    unit (living or not), at nobody and at someone unknown; each answer
    around the options, and stopping; ending the turn."""
    ids = [u.unit_id for u in s.combat.allies + s.combat.enemies] + [None, FAKE]
    out = [{"type": "end_turn"}]
    for index in range(-1, len(ally.hand) + 1):
        out.extend({"type": "play_card", "hand_index": index, "target_id": t} for t in ids)
    ask = s.combat.choice_for(ally)
    count = len(ask.options) if ask is not None else 0
    out.extend({"type": "choose", "option_index": i} for i in range(-2, count + 1))
    return out


def normalised(s, ally, action):
    """A target sent to a card that picks its own is ignored - the same action
    as sending none."""
    if action["type"] != "play_card" or action["target_id"] in (None, FAKE):
        return action
    if not (0 <= action["hand_index"] < len(ally.hand)):
        return action
    if create_card(ally.hand[action["hand_index"]]).target_type in (TargetType.ENEMY, TargetType.ALLY):
        return action
    return dict(action, target_id=None)


key = lambda a: json.dumps(a, sort_keys=True)


def trial_copy(s):
    """A copy of the session to try an action on. Its random streams are the
    real ones, shared rather than copied (most of the copying time); restore()
    puts them back as they were after the try."""
    streams = [getattr(s.rngs, name) for name in s.rngs.NAMES]
    saved = [r.getstate() for r in streams]
    trial = copy.deepcopy(s, {id(r): r for r in streams})
    def restore():
        for r, state in zip(streams, saved):
            r.setstate(state)
    return trial, restore
mismatches, decisions, tried, fights = [], 0, 0, 0
seen = {"question": 0, "stop": 0, "teammate": 0, "random": 0}
lineups = [("nibbit",), ("leafslimemedium", "twigslimesmall"), ("flyconid", "nibbit", "wriggler"),
           ("dummy1", "dummy1")]
for seed in range(40):
    rng = random.Random(seed)
    dealt = [rng.choice(PLAYABLE_IDS) for _ in range(12)]
    dealt += [rng.choice(FOR_A_TEAMMATE), rng.choice(ASKS)]
    LegalProbe.DEFAULT_DECK = [CardRef(i, upgraded=rng.random() < 0.3) for i in dealt]
    s = Session(Combat, required_players=1 + seed % 2, seed=seed)
    s.ALLY_TYPE_ID = "legalprobe"
    s.ENEMY_TYPE_IDS = lineups[seed % len(lineups)]
    s.SCALE_ENEMIES = False
    for i in range(s.required_players):
        s.add_player("sid%d" % i)
    fights += 1
    for _step in range(120):
        if not s.is_running():
            break
        sids = [sid for sid in s.players if s.combat.legal_actions(s.players[sid])
                and sid not in s.ready]
        if not sids:
            sids = [sid for sid in s.players if s.combat.legal_actions(s.players[sid])]
        if not sids:
            break
        sid = rng.choice(sids)
        ally = s.players[sid]
        listed = s.combat.legal_actions(ally)
        listed_keys = {key(a) for a in listed}
        decisions += 1
        ask = s.combat.choice_for(ally)
        seen["question"] += ask is not None
        seen["stop"] += ask is not None and ask.can_stop
        seen["teammate"] += any(a.get("target_id", "").startswith("p") for a in listed
                                if a.get("target_id"))
        seen["random"] += any(a["type"] == "play_card" and create_card(ally.hand[a["hand_index"]])
                              .target_type in (TargetType.RANDOM_ENEMY, TargetType.RANDOM_ALLY)
                              for a in listed)
        for action in candidates(s, ally):
            trial, restore = trial_copy(s)
            answer = refused(trial.handle(sid, as_message(action)), sid)
            restore()
            accepted = "crash" if answer == "crash" else not answer
            tried += 1
            expected = key(normalised(s, ally, action)) in listed_keys
            if accepted is not expected:
                mismatches.append((seed, ally.unit_id, [str(c) for c in ally.hand], action, accepted))
        # Then the fight moves on, by an action from the list: mostly plays.
        options = [a for a in listed if a["type"] != "end_turn"]
        action = rng.choice(options) if options and rng.random() < 0.85 else rng.choice(listed)
        if refused(s.handle(sid, as_message(action)), sid):
            mismatches.append((seed, ally.unit_id, "the listed action taken was refused", action))

# A defeated player: nothing listed, and nothing they send is taken - end turn included.
s = Session(Combat, required_players=2, seed=3)
s.ENEMY_TYPE_IDS = ("nibbit",)
s.add_player("sid0")
s.add_player("sid1")
s.players["sid1"].current_hp = 0
dead = s.players["sid1"]
taken = [a for a in candidates(s, dead) if not refused(copy.deepcopy(s).handle("sid1", as_message(a)), "sid1")]
check("a defeated player: nothing listed, and every action refused",
      s.combat.legal_actions(dead) == [] and taken == [], taken[:3])

print("%d fights, %d decision points, %d actions tried; decisions with %s" % (
    fights, decisions, tried, ", ".join("%s %d" % kv for kv in seen.items())))
check("every listed action accepted, every other refused", not mismatches, mismatches[:5])
check("the fights reached plenty of decisions, questions and teammate targets among them",
      decisions > 500 and seen["question"] > 10 and seen["stop"] and seen["teammate"] > 10
      and seen["random"], (decisions, seen))

print()
print("%d checks failed" % len(bad))
for label in bad:
    print("   ", label)

import sys as _sys
_sys.exit(1 if bad else 0)
