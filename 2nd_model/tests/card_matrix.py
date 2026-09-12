# -*- coding: utf-8 -*-
"""Play one card through every situation and show exactly what it did.

    python tests/card_matrix.py                the card named in CARD below
    python tests/card_matrix.py bash           another card, no edit needed
    python tests/card_matrix.py bash --save    approve this table: it is saved
                                               to tests/golden/bash.json and
                                               every later run is compared
                                               against it
    python tests/card_matrix.py all            every card in the registry;
                                               prints only what failed
    python tests/card_matrix.py bash --enemy=aeonglass
                                               against another enemy

Every row is a fresh fight from the same seed. A legal row shows three
diffs: the play itself, a Strike played straight after it (for anything
the card does to the next Attack), and the end of the turn (which includes
the enemy's move - for Powers, and for anything held in hand at turn end).
An illegal row must be refused with an error message and leave the fight
exactly as it was; being allowed is the failure. Every row is run twice
and must come out identical.

Checks that fail the run: a crash, an illegal move allowed, a refusal that
changed something, a copy of the card in two piles at once, HP / Block /
energy below zero, a result that disagrees with who is alive, state that
does not serialise, a row that comes out differently the second time, and
a diff that no longer matches the approved table.
"""
import collections
import json
import os
import random
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Server"))

from GameEngine.Combat.combat import Combat, CombatResult
from GameEngine.Registry.unit_registry import create_ally, create_enemy
from GameEngine.Registry.card_registry import create_card, known_card_ids
from GameEngine.Cards._card import Card
from GameEngine.Cards._card_ref import CardRef, new_ref, is_upgraded, replay_of, bonus_of
from GameEngine.Cards._card_enums import CardType, TargetType
from GameEngine.Cards._upgrades import upgrade_for
from GameEngine.Effects.StatusEffects.strength import Strength
from GameEngine.Effects.StatusEffects.dexterity import Dexterity
from GameEngine.Effects.StatusEffects.weak import Weak
from GameEngine.Effects.StatusEffects.frail import Frail
from GameEngine.Effects.StatusEffects.vulnerable import Vulnerable

# ---------------------------------------------------------------- settings --
CARD = "*"        # the card under test; the command line overrides it
ALLIES = (1, 2)        # party sizes to try
ENEMIES = (1, 13)       # enemy counts to try
ENEMY = "dummy1"       # dummy1 / theinsatiable / aeonglass
ENERGY = 3             # raised to the card's cost when it costs more
ENEMY_HP = 500         # nothing dies by accident; "enemy at 1 HP" is where it does
SAVE = False           # True (or --save) approves this card's table
SEED = 7

GOLDEN_DIR = os.path.join(HERE, "golden")
# What Session turns into a private error, rather than a bug.
REFUSAL = (ValueError, IndexError, RuntimeError)
SINGLE_TARGET = (TargetType.ENEMY, TargetType.ALLY)


# ------------------------------------------------------------- the fight ---

def build(n_allies, n_enemies, ref, energy):
    """A fresh fight with the card under test at hand index 0."""
    allies = [create_ally("testally1", "p%d" % (i + 1), rng=random.Random(SEED + i))
              for i in range(n_allies)]
    enemies = [create_enemy(ENEMY, "e%d" % (i + 1), rng=random.Random(SEED + 10 + i))
               for i in range(n_enemies)]
    c = Combat(allies, enemies, rng=random.Random(SEED), scale_enemies=False)
    c.ask_players = True          # questions park, so every option can be tried
    c.start()
    for e in enemies:
        e.current_hp = e.max_hp = ENEMY_HP
    me = allies[0]
    me.hand = [ref, CardRef("strike"), CardRef("defend")]
    me.draw_pile = [CardRef("strike") for _ in range(4)] + [CardRef("defend") for _ in range(3)]
    me.discard_pile = [CardRef("defend") for _ in range(2)]
    me.energy = me.max_energy = energy
    return c


def label(ref):
    text = str(ref)
    if is_upgraded(ref):
        text += "+"
    if bonus_of(ref):
        text += "(+%d)" % bonus_of(ref)
    if replay_of(ref):
        text += " x%d" % (replay_of(ref) + 1)
    return text


def snap(c):
    state = {
        "phase": c.phase.name,
        "result": c.result.name if c.result is not None else None,
        "choices": {uid: (ask.prompt, [str(o) for o in ask.options])
                    for uid, ask in c.pending_choices.items()},
        "units": {},
    }
    for u in c.allies + c.enemies:
        row = {"hp": u.current_hp, "block": u.block,
               "statuses": {k: v.amount for k, v in u.statuses.items()}}
        if u in c.allies:
            row["energy"] = u.energy
            for pile in ("hand", "draw_pile", "discard_pile", "exhaust_pile"):
                row[pile] = collections.Counter(label(x) for x in getattr(u, pile))
        state["units"][u.unit_id] = row
    return state


PILE_NAMES = {"hand": "hand", "draw_pile": "draw", "discard_pile": "discard",
              "exhaust_pile": "exhaust"}


def diff(before, after, names=True):
    """What changed, as short strings grouped by unit. Empty when nothing did."""
    out = []
    for uid, b in before["units"].items():
        a = after["units"][uid]
        bits = []
        if a["hp"] != b["hp"]:
            bits.append("hp %+d" % (a["hp"] - b["hp"]))
        if a["block"] != b["block"]:
            bits.append("block %d->%d" % (b["block"], a["block"]))
        for key in sorted(set(b["statuses"]) | set(a["statuses"])):
            was, now = b["statuses"].get(key), a["statuses"].get(key)
            if was == now:
                continue
            if was is None:
                bits.append("+%s %s" % (key, now))
            elif now is None:
                bits.append("-%s" % key)
            else:
                bits.append("%s %s->%s" % (key, was, now))
        if "energy" in b and a["energy"] != b["energy"]:
            bits.append("energy %d->%d" % (b["energy"], a["energy"]))
        for pile, short in PILE_NAMES.items():
            if pile not in b or a[pile] == b[pile]:
                continue
            if names:
                gone = sorted((b[pile] - a[pile]).elements())
                came = sorted((a[pile] - b[pile]).elements())
                bits.append("%s %s" % (short, " ".join(
                    ["-" + x for x in gone] + ["+" + x for x in came])))
            else:
                bits.append("%s %d->%d" % (short, sum(b[pile].values()),
                                            sum(a[pile].values())))
        if bits:
            out.append("%s: %s" % (uid, ", ".join(bits)))
    if after["result"] != before["result"]:
        out.append("result %s" % after["result"])
    for uid, (prompt, options) in after["choices"].items():
        if before["choices"].get(uid) != (prompt, options):
            out.append("%s asked: %s %s" % (uid, prompt, options))
    return out


def where_is(c, ref, card):
    """Which pile the played copy sits in now, by identity."""
    hits = []
    for ally in c.allies:
        for pile, short in PILE_NAMES.items():
            if any(x is ref for x in getattr(ally, pile)):
                hits.append(short if ally is c.allies[0] else "%s %s" % (ally.unit_id, short))
    if len(hits) > 1:
        return "IN %d PILES: %s" % (len(hits), ", ".join(hits)), True
    if hits:
        return hits[0], False
    if card.card_type is CardType.POWER:
        return "power (no pile)", False
    return "gone", False


def sanity(c, phase, fails):
    """The invariants nothing is allowed to break, whatever the card."""
    for u in c.allies + c.enemies:
        if u.current_hp < 0:
            fails.append("%s: %s hp below zero (%d)" % (phase, u.unit_id, u.current_hp))
        if u.block < 0:
            fails.append("%s: %s block below zero (%d)" % (phase, u.unit_id, u.block))
        if u in c.allies and u.energy < 0:
            fails.append("%s: %s energy below zero (%d)" % (phase, u.unit_id, u.energy))
    enemies_up = any(e.is_alive() for e in c.enemies)
    allies_up = any(a.is_alive() for a in c.allies)
    if c.result is CombatResult.VICTORY and enemies_up:
        fails.append("%s: VICTORY with an enemy still alive" % phase)
    if c.result is CombatResult.DEFEAT and allies_up:
        fails.append("%s: DEFEAT with an ally still alive" % phase)
    if c.result is None and not (enemies_up and allies_up):
        fails.append("%s: a side is dead but the fight is not over" % phase)
    try:
        json.dumps(c.to_dict())
    except Exception as error:
        fails.append("%s: to_dict does not serialise: %s" % (phase, error))


def footprint(card, me, target, c):
    """Who a card of this target type is entitled to touch."""
    tt = card.target_type
    if tt is TargetType.SELF:
        return {me.unit_id}
    if tt in SINGLE_TARGET:
        return {me.unit_id, target.unit_id if target is not None else None}
    if tt in (TargetType.ALL_ENEMIES, TargetType.RANDOM_ENEMY):
        return {me.unit_id} | {e.unit_id for e in c.enemies}
    return {a.unit_id for a in c.allies}


def answer_all(c, me, first=None):
    """Answer what is pending: the chosen option for `me`'s first question,
    option 0 for anything after it (and for anybody else)."""
    answered = []
    guard = 0
    while c.pending_choices and guard < 30:
        guard += 1
        uid, ask = next(iter(c.pending_choices.items()))
        pick = first if (uid == me.unit_id and first is not None) else 0
        first = None if uid == me.unit_id else first
        answered.append("%s: %s -> %s" % (uid, ask.prompt, ask.options[pick]))
        c.answer_choice(c.find_unit(uid), pick)
    return answered


def strike_index(me, ref):
    for i, held in enumerate(me.hand):
        if str(held) == "strike" and held is not ref:
            return i
    return None


# ------------------------------------------------------------------ rows ----

class Row:
    def __init__(self, name, allies, enemies, upgraded=False, target=None,
                 setup=None, expect=None, index=0, pre=None, illegal=None):
        self.name = name
        self.allies = allies
        self.enemies = enemies
        self.upgraded = upgraded
        self.target = target          # fn(c) -> unit or None
        self.setup = setup            # fn(c, me, foe, ref), before the play
        self.expect = expect          # (ExceptionType, fragment) for an illegal row
        self.index = index            # hand index to play
        self.pre = pre                # legal steps before the illegal one
        self.illegal = illegal        # fn(c, me, ref, target); default: the play


def run_row(row, card_id, energy, answer=None):
    """One fresh fight. Returns a dict with the phases, fails, and notes."""
    ref = CardRef(card_id, upgraded=row.upgraded)
    c = build(row.allies, row.enemies, ref, energy)
    me, foe = c.allies[0], c.enemies[0]
    card = create_card(ref)
    if row.setup is not None:
        row.setup(c, me, foe, ref)
    target = row.target(c) if row.target is not None else None
    result = {"phases": {}, "fails": [], "notes": [], "options": None}
    fails = result["fails"]

    # ---- an illegal row: it has to be refused, and change nothing --------
    if row.expect is not None:
        if not card.playable_now(me):
            # Clash wants a hand of Attacks; give it one, or its own refusal
            # would pre-empt the one this row is about.
            me.hand = [ref, CardRef("strike"), CardRef("strike")]
        if row.pre is not None:
            row.pre(c, me, ref, target)
        before = snap(c)
        exc_type, fragment = row.expect
        try:
            if row.illegal is not None:
                row.illegal(c, me, ref, target)
            else:
                c.play_card(me, row.index, target=target)
        except exc_type as error:
            message = str(error)
            if fragment not in message:
                fails.append("refused, but for the wrong reason: %s" % message)
            changed = diff(before, snap(c))
            if changed:
                fails.append("refused, yet something changed: %s" % "; ".join(changed))
            result["phases"]["refused"] = [message]
        except REFUSAL as error:
            fails.append("refused with %s instead of %s: %s"
                         % (type(error).__name__, exc_type.__name__, error))
            result["phases"]["refused"] = [str(error)]
        except Exception:
            fails.append("CRASH: " + traceback.format_exc().strip().splitlines()[-1])
        else:
            fails.append("ALLOWED - should have been refused")
            result["phases"]["allowed"] = diff(before, snap(c))
        return result

    # ---- phase 1: the play -----------------------------------------------
    before = snap(c)
    played = True
    try:
        c.play_card(me, row.index, target=target)
    except REFUSAL as error:
        played = False
        changed = diff(before, snap(c))
        if changed:
            fails.append("refused, yet something changed: %s" % "; ".join(changed))
        result["phases"]["play"] = ["REFUSED: %s" % error]
    except Exception:
        fails.append("CRASH on play: " + traceback.format_exc().strip().splitlines()[-1])
        return result

    if played:
        if me.unit_id in c.pending_choices and answer is None:
            # The caller runs this row once per option instead.
            result["options"] = list(c.pending_choices[me.unit_id].options)
            return result
        try:
            answered = answer_all(c, me, first=answer)
        except Exception:
            fails.append("CRASH answering: " + traceback.format_exc().strip().splitlines()[-1])
            return result
        after = snap(c)
        lines = diff(before, after)
        place, duplicated = where_is(c, ref, card)
        lines.insert(0, "%s -> %s" % (label(ref), place))
        if duplicated:
            fails.append("the played copy is in two piles at once")
        lines.extend("answered " + a for a in answered)
        allowed = footprint(card, me, target, c)
        for line in diff(before, after):
            uid = line.split(":")[0]
            if uid in before["units"] and uid not in allowed:
                result["notes"].append("outside its target: " + line)
        result["phases"]["play"] = lines
        sanity(c, "play", fails)

    # ---- phase 2: a Strike straight after ---------------------------------
    if not c.is_over():
        idx = strike_index(me, ref)
        living = [e for e in c.enemies if e.is_alive()]
        if idx is None or not living:
            result["phases"]["strike"] = ["(no Strike in hand)" if idx is None
                                          else "(no enemy left)"]
        else:
            before = snap(c)
            try:
                c.play_card(me, idx, target=living[0])
                answer_all(c, me)
                result["phases"]["strike"] = diff(before, snap(c))
                sanity(c, "strike", fails)
            except REFUSAL as error:
                result["phases"]["strike"] = ["REFUSED: %s" % error]
            except Exception:
                fails.append("CRASH on the Strike after: "
                             + traceback.format_exc().strip().splitlines()[-1])
                return result

    # ---- phase 3: end of turn, enemy move included -------------------------
    if not c.is_over():
        moves = []
        for e in c.enemies:
            if e.is_alive():
                intent = e.intent if isinstance(e.intent, dict) else {}
                moves.append("%s %s" % (e.unit_id, intent.get("name") or intent.get("type")))
        before = snap(c)
        try:
            c.end_player_turn()
            lines = diff(before, snap(c), names=False)
            result["phases"]["turn"] = ["enemy: " + ", ".join(moves)] + lines
            sanity(c, "turn", fails)
        except REFUSAL as error:
            result["phases"]["turn"] = ["REFUSED: %s" % error]
        except Exception:
            fails.append("CRASH at end of turn: "
                         + traceback.format_exc().strip().splitlines()[-1])
    return result


# ---------------------------------------------------------- the matrix ------

def aims(target_type, n_allies, n_enemies):
    """Who to aim at in a cell: every legal pick, so each gets a row."""
    if target_type is TargetType.ENEMY:
        return [((lambda c, i=i: c.enemies[i]), " -> e%d" % (i + 1)) for i in range(n_enemies)]
    if target_type is TargetType.ALLY:
        if n_allies == 1:
            return [((lambda c: c.allies[0]), " -> self")]
        return [((lambda c, i=i: c.allies[i]), " -> p%d" % (i + 1)) for i in range(1, n_allies)]
    return [(None, "")]


def status(cls, on, amount=2):
    def apply(c, me, foe, ref):
        who = me if on == "me" else foe
        other = foe if on == "me" else me
        who.apply_status(cls(source=other, target=who, amount=amount))
    return apply


def stacked(c, me, foe, ref):
    status(Strength, "me")(c, me, foe, ref)
    status(Weak, "me")(c, me, foe, ref)
    status(Vulnerable, "foe")(c, me, foe, ref)


def set_hand(*ids):
    def apply(c, me, foe, ref):
        me.hand = [ref] + [new_ref(ref) if x == "COPY" else CardRef(x) for x in ids]
    return apply


def set_attr(who, name, value):
    def apply(c, me, foe, ref):
        setattr(me if who == "me" else foe, name, value)
    return apply


def empty_piles(*piles):
    def apply(c, me, foe, ref):
        for pile in piles:
            setattr(me, pile, [])
    return apply


def with_replay(c, me, foe, ref):
    ref.replay = 1


MODIFIERS = [
    ("2 Strength", status(Strength, "me")),
    ("Weak", status(Weak, "me")),
    ("2 Dexterity", status(Dexterity, "me")),
    ("Frail", status(Frail, "me")),
    ("enemy Vulnerable", status(Vulnerable, "foe")),
    ("2 Strength + Weak + enemy Vulnerable", stacked),
    ("enemy has 5 Block", set_attr("foe", "block", 5)),
    ("self has 5 Block", set_attr("me", "block", 5)),
    ("enemy at 1 HP", set_attr("foe", "current_hp", 1)),
    ("self at 1 HP", set_attr("me", "current_hp", 1)),
    ("hand is all Attacks", set_hand("strike", "strike")),
    ("second copy in hand", set_hand("COPY", "strike", "defend")),
    # Ten others: the card leaves the hand before it resolves, so a hand of
    # ten is nine by the time it draws. This one stays full.
    ("hand full (10 others)", set_hand(*["strike"] * 10)),
    ("empty draw pile", empty_piles("draw_pile")),
    ("empty draw and discard", empty_piles("draw_pile", "discard_pile")),
    ("copy has Replay 1", with_replay),
]


def kill_all_enemies(c, me, foe, ref):
    for e in c.enemies:
        e.current_hp = 0
    c._check_combat_end()


def rows_for(card_id, card):
    tt = card.target_type
    rows = []
    for na in ALLIES:
        for ne in ENEMIES:
            for up in (False, True):
                for aim, tag in aims(tt, na, ne):
                    rows.append(Row("%dv%d %s%s" % (na, ne, "upgraded" if up else "plain", tag),
                                    na, ne, up, aim))
    na, ne = ALLIES[0], ENEMIES[0]
    aim, tag = aims(tt, na, ne)[0]
    for name, setup in MODIFIERS:
        rows.append(Row("%dv%d + %s%s" % (na, ne, name, tag), na, ne, False, aim, setup))
    if card.cost == Card.X_COST:
        rows.append(Row("%dv%d + 0 energy (X = 0)%s" % (na, ne, tag), na, ne, False, aim,
                        set_attr("me", "energy", 0)))

    # ---- illegal moves --------------------------------------------------
    ill = []
    if tt in SINGLE_TARGET:
        # ALLY cards need somebody else to aim at, or "dead target" is "dead player".
        ina = na if tt is TargetType.ENEMY else max(ALLIES)
        aim, tag = aims(tt, ina, ne)[0]
        if tt is TargetType.ENEMY:
            wrong, other = "an enemy card aimed at an ally", (lambda c: c.allies[0])
        else:
            wrong, other = "an ally card aimed at an enemy", (lambda c: c.enemies[0])
        ill.append(Row("no target given", ina, ne, target=None,
                       expect=(ValueError, "requires a target")))
        if tt is TargetType.ENEMY or ina > 1:
            ill.append(Row("target already dead%s" % tag, ina, ne, target=aim,
                           setup=lambda c, me, foe, ref, aim=aim: setattr(aim(c), "current_hp", 0),
                           expect=(ValueError, "already been defeated")))
        ill.append(Row("target in the wrong pool (%s)" % wrong, ina, ne, target=other,
                       expect=(ValueError, "is not a valid")))
        if tt is TargetType.ALLY:
            ill.append(Row("aimed at yourself", ina, ne, target=lambda c: c.allies[0],
                           expect=(ValueError, "must target another player")))
    aim, tag = aims(tt, na, ne)[0]
    if isinstance(card.cost, int) and card.cost > 0:
        ill.append(Row("0 energy", na, ne, target=aim, setup=set_attr("me", "energy", 0),
                       expect=(ValueError, "Not enough energy")))
    ill.append(Row("hand index out of range", na, ne, target=aim, index=99,
                   expect=(IndexError, "out of range")))
    ill.append(Row("player already dead", na, ne, target=aim,
                   setup=set_attr("me", "current_hp", 0), expect=(ValueError, "cannot act")))
    ill.append(Row("combat already over", na, ne, target=aim, setup=kill_all_enemies,
                   expect=(RuntimeError, "not the player turn")))
    return rows, ill


def choice_rows(card, na, ne, aim):
    """Illegal moves that only exist once a card has asked a question."""
    def play(c, me, ref, target):
        c.play_card(me, 0, target=target)

    def another(c, me, ref, target):
        c.play_card(me, 0, target=c.enemies[0])

    return [
        Row("play another card before answering", na, ne, target=aim, pre=play,
            illegal=another, expect=(ValueError, "has a choice to answer first")),
        Row("end the turn before answering", na, ne, target=aim, pre=play,
            illegal=lambda c, me, ref, target: c.end_player_turn(),
            expect=(RuntimeError, "Still waiting on a choice")),
        Row("answer an option that does not exist", na, ne, target=aim, pre=play,
            illegal=lambda c, me, ref, target: c.answer_choice(me, 99),
            expect=(IndexError, "out of range")),
    ]


def run_matrix(card_id):
    """Every row for one card, choice forks included, each run twice."""
    card = create_card(card_id)
    energy = ENERGY
    if isinstance(card.cost, int) and card.cost > ENERGY:
        energy = card.cost
    legal, illegal = rows_for(card_id, card)
    results = []          # (row name, result)
    asked_once = False

    def run_twice(row, answer=None):
        first = run_row(row, card_id, energy, answer)
        if first["options"] is not None:
            return first
        second = run_row(row, card_id, energy, answer)
        if first["phases"] != second["phases"]:
            first["fails"].append("not deterministic: second run differed")
        return first

    for row in legal:
        out = run_twice(row)
        if out["options"] is not None:
            if not asked_once:
                asked_once = True
                illegal.extend(choice_rows(card, row.allies, row.enemies, row.target))
            for i, option in enumerate(out["options"]):
                forked = run_twice(row, answer=i)
                results.append(("%s  choice[%d]=%s" % (row.name, i, option), forked))
        else:
            results.append((row.name, out))
    for row in illegal:
        results.append(("ILLEGAL " + row.name, run_twice(row)))
    return card, energy, results


# ---------------------------------------------------------------- golden ----

def config():
    return {"allies": list(ALLIES), "enemies": list(ENEMIES), "enemy": ENEMY,
            "energy": ENERGY, "enemy_hp": ENEMY_HP, "seed": SEED}


def golden_path(card_id):
    return os.path.join(GOLDEN_DIR, "%s.json" % card_id)


def compare_golden(card_id, results):
    """Lines describing how this run differs from the approved table."""
    path = golden_path(card_id)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        saved = json.load(handle)
    if saved.get("config") != config():
        return ["approved under a different setup %s - not compared" % saved.get("config")]
    lines = []
    seen = set()
    for name, out in results:
        seen.add(name)
        was = saved["rows"].get(name)
        if was is None:
            lines.append("new row: %s" % name)
        elif was != out["phases"]:
            for phase in sorted(set(was) | set(out["phases"])):
                if was.get(phase) != out["phases"].get(phase):
                    lines.append("%s | %s\n        approved: %s\n        now     : %s"
                                 % (name, phase, was.get(phase), out["phases"].get(phase)))
    for name in saved["rows"]:
        if name not in seen:
            lines.append("row gone: %s" % name)
    return lines


def save_golden(card_id, results):
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    data = {"card": card_id, "config": config(),
            "rows": {name: out["phases"] for name, out in results}}
    with open(golden_path(card_id), "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True)


# ---------------------------------------------------------------- report ----

def describe(card, energy):
    props = [k for k, v in vars(card.properties).items() if v and k != "playable"]
    if not card.properties.playable:
        props.append("UNPLAYABLE")
    table = card.UPGRADE if card.UPGRADE is not None else upgrade_for(card.card_id)
    print("%s  |  %s  cost %s  target %s%s%s" % (
        card.name, card.card_type.name.title(), card.cost, card.target_type.name,
        "  DAMAGE %d" % card.DAMAGE if card.DAMAGE else "",
        "  [%s]" % ", ".join(props) if props else ""))
    print("upgrade : %s" % (table or "(no change)"))
    print("setup   : allies %s, enemies %s, %s at %d HP, energy %d, seed %d"
          % (ALLIES, ENEMIES, ENEMY, ENEMY_HP, energy, SEED))
    print()


def print_table(results):
    width = max(len(name) for name, _ in results)
    for number, (name, out) in enumerate(results, 1):
        flag = "!!" if out["fails"] else "  "
        print("%s[%2d] %s" % (flag, number, name.ljust(width)))
        for phase, lines in out["phases"].items():
            print("       %-7s %s" % (phase, "; ".join(lines) if lines else "(nothing changed)"))
        for note in out["notes"]:
            print("       ??      %s" % note)
        for fail in out["fails"]:
            print("       FAIL    %s" % fail)


def single(card_id, save):
    try:
        card, energy, results = run_matrix(card_id)
    except KeyError:
        print("unknown card id %r - known ids look like: %s ..."
              % (card_id, ", ".join(known_card_ids()[:8])))
        return 2
    describe(card, energy)
    print_table(results)
    failed = sum(1 for _, out in results if out["fails"])
    print()
    print("rows: %d   failed: %d   notes: %d" % (
        len(results), failed, sum(len(out["notes"]) for _, out in results)))
    drift = compare_golden(card_id, results)
    if save:
        save_golden(card_id, results)
        print("approved: saved to %s" % os.path.relpath(golden_path(card_id), HERE))
    elif drift is None:
        print("no approved table yet - run with --save once this reads right")
    elif drift:
        print("CHANGED since approved (%d):" % len(drift))
        for line in drift:
            print("   ~~ " + line)
    else:
        print("matches the approved table")
    return 1 if failed or (drift and not save) else 0


def everything():
    started = time.time()
    broken = {}
    drifted = {}
    noted = {}
    rows = 0
    for card_id in known_card_ids():
        try:
            _, _, results = run_matrix(card_id)
        except Exception:
            broken[card_id] = ["CRASH building the matrix: "
                               + traceback.format_exc().strip().splitlines()[-1]]
            continue
        rows += len(results)
        fails = ["%s: %s" % (name, f) for name, out in results for f in out["fails"]]
        if fails:
            broken[card_id] = fails
        notes = sorted({n for _, out in results for n in out["notes"]})
        if notes:
            noted[card_id] = notes
        drift = compare_golden(card_id, results)
        if drift:
            drifted[card_id] = drift
    for card_id, fails in broken.items():
        print("%-22s %d failing" % (card_id, len(fails)))
        for f in fails[:6]:
            print("    - " + f)
        if len(fails) > 6:
            print("    - ... %d more" % (len(fails) - 6))
    for card_id, lines in drifted.items():
        print("%-22s %d changed since approved" % (card_id, len(lines)))
        for line in lines[:3]:
            print("    ~~ " + line.splitlines()[0])
    if noted:
        # Not failures: a card reaching past its declared target. Worth a look
        # once, and a real bug when the card text does not say so.
        print("touching units outside their target type (read once, not failures):")
        for card_id, notes in noted.items():
            print("    %-22s %s" % (card_id, notes[0][len("outside its target: "):]))
    print()
    print("cards: %d   rows: %d   failing cards: %d   changed since approved: %d   %.1fs"
          % (len(known_card_ids()), rows, len(broken), len(drifted), time.time() - started))
    return 1 if broken or drifted else 0


def main(argv):
    global ENEMY
    save = SAVE or "--save" in argv
    for arg in argv:
        if arg.startswith("--enemy="):
            ENEMY = arg.split("=", 1)[1]
    words = [a for a in argv if not a.startswith("--")]
    card_id = words[0] if words else CARD
    if card_id in ("all", "*"):
        return everything()
    return single(card_id, save)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
