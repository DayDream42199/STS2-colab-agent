"""A combat log's raw lines as turns: for each turn, each player's moves in
the order they made them, and what the aura plugin made of that turn.

    python -m Plugins.turn_export <combat log> [out.json]      (from Server/)

prints the fight a turn at a time and writes it to <log name>_turns.json next
to the log (or to out.json), one JSON object:

    seed, act, enemies, result     from combat_start and combat_end
    players     {unit_id: {role, deck}}
    aura        where the aura plugin's turns came from: "logged", "rebuilt"
                (history_export.load replayed the fight with the plugin on,
                for a log written without it) or null (none: no round ended)
    turns       one per turn, in order:
        turn        its number
        state       the state as it began (player format, as logged)
        players     {unit_id: {moves, analyzer_input, profile_update}}
        other       any other line that fell in it (an error, a plugin's own)
    end_state   the state the fight ended in

A move is its log line with "event" named "move" (play, choose, end_turn,
wait, refused, left), less time, unit_id and role; nothing else is dropped.
Its seq says where it fell among everyone's moves, since the players move at
the same time. analyzer_input and profile_update are the aura plugin's lines
for that player's turn, less the fields said already; null for a turn it did
not score (the agent's, one never ended).
"""
import json
import os
import sys

from .history_export import load

MOVES = ("play", "choose", "end_turn", "wait", "refused", "left")
AURA = ("analyzer_input", "profile_update")
SETUP = ("join", "identify", "combat_start", "turn_start", "round_end", "combat_end")


def turns(lines):
    """The fight in a log's lines, turn by turn: the JSON above."""
    start = next((l for l in lines if l["event"] == "combat_start"), {})
    fight = {"seed": start.get("seed"), "act": start.get("act"), "enemies": start.get("enemy_types"),
             "result": None, "aura": None,
             "players": {p["unit_id"]: {"role": p["role"], "deck": p["deck"]} for p in start.get("players", [])},
             "turns": [], "end_state": None}
    by_number = {}

    def turn(number, state=None):
        if number not in by_number:
            by_number[number] = {"turn": number, "state": state, "players": {}, "other": []}
            fight["turns"].append(by_number[number])
        return by_number[number]

    def player(entry, unit_id):
        return entry["players"].setdefault(
            unit_id, {"moves": [], "analyzer_input": None, "profile_update": None})

    current = None
    for line in lines:
        event = line["event"]
        if event == "identify" and line["unit_id"] in fight["players"]:
            fight["players"][line["unit_id"]]["role"] = line["role"]
        elif event == "turn_start":
            current = turn(line["turn"], line["state"])
            for unit_id in fight["players"]:
                player(current, unit_id)              # everyone, moves or not
        elif event == "combat_end":
            fight["result"], fight["end_state"] = line["result"], line["state"]
        elif event in MOVES and line.get("unit_id") is not None:
            move = {"move": event}
            move.update((k, v) for k, v in line.items() if k not in ("event", "time", "unit_id", "role"))
            # A move before the first turn began goes in a turn 0.
            player(current or turn(0), line["unit_id"])["moves"].append(move)
        elif event in AURA:
            said = ("seq", "time", "event", "unit_id", "turn", "rebuilt")
            player(turn(line["turn"]), line["unit_id"])[event] = {
                k: v for k, v in line.items() if k not in said}
            fight["aura"] = "rebuilt" if line.get("rebuilt") else "logged"
        elif event not in SETUP:
            (current or turn(0))["other"].append({k: v for k, v in line.items() if k != "time"})
    return fight


# --- as text ------------------------------------------------------------------

def _card(card_id, upgraded=False):
    return " ".join(w.capitalize() for w in str(card_id).split("_")) + ("+" if upgraded else "")


def _result(r):
    """One thing a move did, short."""
    if not isinstance(r, dict):
        return str(r)
    effect, target = r.get("effect_id", "?"), r.get("target_id")
    if effect == "instant_damage":
        # total is the whole swing, amount what got through Block.
        notes = []
        if r.get("amount") != r.get("total"):
            notes.append("%s through Block" % r.get("amount"))
        notes.append("killed" if r.get("killed") else "%s HP left" % r.get("target_hp"))
        return "%s to %s (%s)" % (r.get("total"), target, ", ".join(notes))
    if effect == "instant_block":
        return "+%s Block%s" % (r.get("amount"), "" if target == r.get("source_id") else " on %s" % target)
    text = effect.replace("_", " ")
    if r.get("amount") not in (None, 0):
        text += " %s" % r["amount"]
    return text + ("" if target in (None, r.get("source_id")) else " on %s" % target)


def _aimed(move):
    """Whether the play had a target: a client may send one with a card that
    takes none (a Defend "on e2"), and the game ignores it. The actions open
    before the play say which it was."""
    if move.get("target_id") is None:
        return False
    legal = move.get("legal_actions")
    if not legal:
        return True
    return any(a.get("type") == "play_card" and a.get("hand_index") == move.get("hand_index")
               and a.get("target_id") is not None for a in legal)


def _move(move):
    kind = move["move"]
    if kind == "play":
        text = _card(move.get("card_id"), move.get("upgraded"))
        if _aimed(move):
            text += " -> %s" % move["target_id"]
        done = ", ".join(_result(r) for r in move.get("results") or [])
        return "%-22s %s" % (text, done) if done else text
    if kind == "choose":
        option = move.get("option")
        return "chose %s (%s)" % (option if option is not None else "nothing, stopped", move.get("prompt"))
    if kind == "refused":
        return "refused: %s" % move.get("error")
    return {"end_turn": "end turn", "wait": "wait", "left": "left the fight"}.get(kind, kind)


def _enemy(e):
    intent = e.get("intent") or {}
    plan = intent.get("name") or intent.get("type") or ""
    if "attack" in str(intent.get("type")) and intent.get("amount") is not None:
        hits = intent.get("hits") or 1
        plan += " %s%s" % (intent["amount"], "x%d" % hits if hits > 1 else "")
    return "%s %s %s/%s%s" % (e["unit_id"], e.get("name"), e.get("current_hp"), e.get("max_hp"),
                              ": " + plan if plan else "")


def _ally(a):
    upgraded = a.get("hand_upgraded") or []
    hand = [_card(c, i < len(upgraded) and upgraded[i]) for i, c in enumerate(a.get("hand", []))]
    block = ", %s Block" % a["block"] if a.get("block") else ""
    return "%s/%s HP%s, %s energy; hand %s" % (a.get("current_hp"), a.get("max_hp"), block, a.get("energy"),
                                               ", ".join(hand) or "empty")


def _aura(p):
    given, scored = p["analyzer_input"], p["profile_update"]
    if not scored:
        return None
    x = scored["profile"]
    sure = " / ".join("%s%%" % (round(x["c" + t] * 1000) / 10) for t in "AST")
    head = "%s coming, ended on %s Block -> " % (given["incoming"], given["block"]) if given else ""
    return "aura: %sA %+.2f  S %+.2f  T %+.2f  (confidence %s)" % (head, x["A"], x["S"], x["T"], sure)


def show(fight):
    """The fight as text, a turn at a time."""
    who = ", ".join("%s (%s)" % (u, p.get("role")) for u, p in fight["players"].items())
    rows = ["seed %s, %s: %s vs %s - %s" % (fight["seed"], fight["act"], who,
                                           ", ".join(fight["enemies"] or []), fight["result"] or "unfinished"),
            "aura turns: %s" % (fight["aura"] or "none")]
    for entry in fight["turns"]:
        state = entry["state"] or {}
        enemies = [_enemy(e) for e in state.get("enemies", []) if e.get("current_hp", 1) > 0]
        rows += ["", "  |  ".join(["Turn %s" % entry["turn"]] + enemies)]
        allies = {a["unit_id"]: a for a in state.get("allies", [])}
        for unit_id, p in entry["players"].items():
            rows.append("  %s  %s" % (unit_id, _ally(allies[unit_id]) if unit_id in allies else ""))
            rows += ["      #%-4s %s" % (m.get("seq"), _move(m)) for m in p["moves"]]
            aura = _aura(p)
            if aura:
                rows.append("            " + aura)
        rows += ["  %s: %s" % (o["event"], o.get("error") or o.get("message") or "") for o in entry["other"]]
    if fight["result"]:
        rows += ["", "Result: %s" % fight["result"]]
    return "\n".join(rows)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    log = sys.argv[1]
    lines, note = load(log)
    fight = turns(lines)
    print(show(fight))
    if note:
        print("\n" + note)
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(log)[0] + "_turns.json"
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(fight, handle)
    print("\nwritten: %s (%d turns)" % (os.path.abspath(out), len(fight["turns"])))
