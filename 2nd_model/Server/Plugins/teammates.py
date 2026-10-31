"""Scripted teammates: five ways to play, for checking the Characteristic
Analyzer against players whose style is known - and later for the agent to
play alongside.

    aggressive  damage first, Block last
    defensive   Block first, damage last
    scaling     Powers first
    team        team cards first - those that do nothing for yourself, then
                the rest; a card for a teammate or every unit before one hit
    random      any open action, at random

Each picks from Combat.legal_actions, so whatever it sends is accepted. A
styled bot plays its preferred cards first and then whatever else it can
afford, and ends its turn when nothing is left: a style, not a refusal to
play the rest. Attacks go at the weakest enemy, a card for a teammate to the
weakest teammate, and a question gets its first option. Bots never wait.

    python -m Plugins.teammates [fights per pairing]      (from Server/)

plays every pairing of the five (two seats each) through the real session
with the aura plugin, all on one deck, and prints what the analyzer made of
each style: over all its turns together, and fight by fight.
"""
import random
import sys

from GameEngine.Combat.combat import Combat
from GameEngine.Registry.unit_registry import register_ally
from GameEngine.Units.Allies.ironclad import Ironclad
from Protocol.enums import ClientMessage
from Protocol.protocol import encode
from plugin_host import PluginGuard
from session import Session

from . import analyzer
from .aura import create_plugin
from .card_groups import describe_hand

STYLES = ("aggressive", "defensive", "scaling", "team", "random")
# The trait each styled bot should stand out on, and which way. Random has
# none: it is a player with no style, not a reference to measure others by.
OWN_TRAIT = {"aggressive": ("A", 1), "defensive": ("A", -1), "scaling": ("S", 1), "team": ("T", 1)}
END = {"type": "end_turn"}

# One deck for every bot, so a difference in profile is a difference in play:
# attacks, Block, Powers, and cards for the team.
DECK = (["strike"] * 3 + ["defend"] * 3
        + ["bash", "shrug_it_off", "iron_wave", "thunderclap",
           "inflame", "feel_no_pain", "juggernaut",
           "coordinate", "shockwave", "rally"])

# Act 1 lineups (both halves), short and long fights.
LINEUPS = (("nibbit", "nibbit"), ("leafslimemedium", "twigslimesmall"),
           ("fuzzywurmcrawler",), ("seapunk",), ("sewerclam",),
           ("twotailedrat", "twotailedrat"))


class TeammateIronclad(Ironclad):
    """The Ironclad, holding DECK."""
    DEFAULT_DECK = list(DECK)


register_ally(TeammateIronclad)


# --- choosing ---------------------------------------------------------------

def _parts(card):
    """All the damage a card in hand deals, the Block it gives, its groups."""
    return (card["damage"] or 0) * card["hits"], card["block"] or 0, set(card["groups"])


def _aggressive(card):
    damage, block, _ = _parts(card)
    return (2 if damage else 0 if block else 1, damage)


def _defensive(card):
    damage, block, _ = _parts(card)
    return (2 if block else 0 if damage else 1, block)


def _scaling(card):
    return (1 if card["type"] == "POWER" else 0, 0)


def _team(card):
    _, _, groups = _parts(card)
    rank = 0 if "team" not in groups else 1 if "self" in groups else 2
    return (rank, card["target"] in ("ALLY", "ALL_ALLIES", "ALL_ENEMIES"))


PREFERENCE = {"aggressive": _aggressive, "defensive": _defensive,
              "scaling": _scaling, "team": _team}


def choose(style, combat, ally, rng):
    """The action this bot takes now, from legal_actions; None if it has none."""
    legal = combat.legal_actions(ally)
    if not legal:
        return None
    if legal[0]["type"] == "choose":                  # a question waits: only answers
        return rng.choice(legal) if style == "random" else legal[0]
    plays = [a for a in legal if a["type"] == "play_card"]
    if style == "random":
        return rng.choice(plays) if plays and rng.random() < 0.8 else END
    if not plays:
        return END
    hand = describe_hand(combat, ally)
    prefer = PREFERENCE[style]

    def target_hp(action):
        unit = combat.find_unit(action["target_id"]) if action["target_id"] else None
        return unit.current_hp if unit is not None else 0

    return max(plays, key=lambda a: (prefer(hand[a["hand_index"]]), -a["hand_index"], -target_hp(a)))


# --- playing a fight ----------------------------------------------------------

class _Lines:
    """A combat log kept in memory: the analyzer's input, without a file."""
    active = False          # nothing extra worked out for it
    path = None
    tag = None

    def __init__(self):
        self.lines = []

    def write(self, event, **data):
        self.lines.append(dict(data, event=event))

    def close(self):
        pass


def play_fight(styles, enemies, seed, steps=1500):
    """One fight, a bot in each seat. Returns a dict per seat: unit_id,
    style, `profile` (what the analyzer held at the end), `turns` (its input,
    each scored turn), and the fight's `result` and `refused` count."""
    lines = _Lines()
    s = Session(Combat, required_players=len(styles), seed=seed,
                plugin=PluginGuard(create_plugin(), "aura"), combat_log=lines)
    s.ALLY_TYPE_ID = TeammateIronclad.type_id()
    s.ENEMY_TYPE_IDS = tuple(enemies)
    sids = ["s%d" % (i + 1) for i in range(len(styles))]
    for sid in sids:
        s.add_player(sid)
    style_of = dict(zip(sids, styles))
    rng = random.Random(seed)
    refused = 0
    for _ in range(steps):
        if not s.is_running():
            break
        sid = _next_to_act(s)
        if sid is None:
            break
        action = choose(style_of[sid], s.combat, s.players[sid], rng)
        out = s.handle(sid, encode(ClientMessage(action["type"]),
                                   **{k: v for k, v in action.items() if k != "type"}))
        refused += any(m["type"] == "error" for to, m in out if to == sid)

    aura = s.plugin.plugin
    seats = []
    for sid in sids:
        unit_id = s.players[sid].unit_id
        seats.append({
            "unit_id": unit_id, "style": style_of[sid],
            "profile": analyzer.values(aura.profiles[unit_id]),
            "turns": [l for l in lines.lines if l["event"] == "analyzer_input" and l["unit_id"] == unit_id],
            "result": s.combat.result.name if s.combat.result else None,
            "refused": refused,
        })
    return seats


def _next_to_act(s):
    """In seat order, the first player with something to do: a question to
    answer, or a turn not yet ended."""
    for sid, ally in s.players.items():
        if not s.combat.legal_actions(ally):
            continue
        if s.combat.choice_for(ally) is not None or ally.unit_id not in s.combat.ended_turn:
            return sid
    return None


def profile_over(turns):
    """One profile built from all these turns in order, as a profile kept
    from fight to fight would be."""
    profile = analyzer.new_profile()
    for turn in turns:
        analyzer.update(profile, analyzer.evidence(turn)[0])
    return analyzer.values(profile)


def run(fights_per_pairing=2, lineups=LINEUPS):
    """Every ordered pairing of the five styles, on each lineup in turn.
    Returns the seats of every fight, in order."""
    seats, seed = [], 0
    for first in STYLES:
        for second in STYLES:
            for _ in range(fights_per_pairing):
                seats.extend(play_fight((first, second), lineups[seed % len(lineups)], seed))
                seed += 1
    return seats


def summary(seats):
    """Per style: seats played, turns scored, the profile over all its turns,
    and the mean of its end-of-fight profiles."""
    out = {}
    for style in STYLES:
        mine = [seat for seat in seats if seat["style"] == style]
        turns = [turn for seat in mine for turn in seat["turns"]]
        ends = [seat["profile"] for seat in mine]
        out[style] = {
            "seats": len(mine), "turns": len(turns), "over_all": profile_over(turns),
            "fight_mean": {k: sum(p[k] for p in ends) / len(ends) for k in analyzer.values(analyzer.new_profile())},
        }
    return out


def fight_by_fight(seats):
    """Per styled bot, from each fight's end profile: in how many fights with
    another style it came out past its partner on its own trait, and in how
    many of its seats with any evidence on that trait (confidence above 0)
    the trait leaned its way."""
    fights = [seats[i:i + 2] for i in range(0, len(seats), 2)]
    out = {}
    for style, (trait, way) in OWN_TRAIT.items():
        row = {"beat": 0, "mixed": 0, "leaned": 0, "with_evidence": 0}
        for pair in fights:
            for me, other in ((pair[0], pair[1]), (pair[1], pair[0])):
                if me["style"] != style:
                    continue
                if me["profile"]["c" + trait] > 0:
                    row["with_evidence"] += 1
                    row["leaned"] += way * me["profile"][trait] > 0
                if other["style"] != style:
                    row["mixed"] += 1
                    row["beat"] += way * me["profile"][trait] > way * other["profile"][trait]
        out[style] = row
    return out


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    seats = run(count)
    found = summary(seats)
    print("%d fights, %d refused actions" % (len(seats) // 2, sum(s["refused"] for s in seats[::2])))
    print("\n%-11s %5s %6s   %-44s   %s" % ("style", "seats", "turns", "all its turns: A S T (confidence)",
                                           "mean at fight end: A S T"))
    for style, row in found.items():
        p, m = row["over_all"], row["fight_mean"]
        print("%-11s %5d %6d   A %+.2f (%.2f)  S %+.2f (%.2f)  T %+.2f (%.2f)   A %+.2f  S %+.2f  T %+.2f" % (
            style, row["seats"], row["turns"], p["A"], p["cA"], p["S"], p["cS"], p["T"], p["cT"],
            m["A"], m["S"], m["T"]))
    print("\nfight by fight, on its own trait:")
    for style, row in fight_by_fight(seats).items():
        trait, way = OWN_TRAIT[style]
        print("  %-10s %s %s: past its partner in %d of %d mixed fights; leaned that way in %d of %d seats "
              "with evidence" % (style, trait, "+" if way > 0 else "-", row["beat"], row["mixed"],
                                 row["leaned"], row["with_evidence"]))
