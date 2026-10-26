# -*- coding: utf-8 -*-
"""Compare our Ironclad cards with the installed game's, value by value.

    python tests/game_diff.py                 report every difference
    python tests/game_diff.py --json out.json also save the game's values

Reads the game's decompiled C# (not in this repo - it is Mega Crit's code):

    dotnet tool install -g ilspycmd --version 9.1.0.7988
    ilspycmd -p -o D:\\sts2_source -r "<game>\\data_sts2_windows_x86_64" "<game>\\data_sts2_windows_x86_64\\sts2.dll"

Set STS2_SOURCE if it lives somewhere else. Not part of run_all.py: nobody else
has the decompiled source. Rerun after a game patch to see what changed.

A card class in the game declares everything this needs in three places:

    base(2, CardType.Attack, CardRarity.Basic, TargetType.AnyEnemy)   cost, type, rarity
    CanonicalVars: new DamageVar(8m), new PowerVar<VulnerablePower>(2m) values
    OnUpgrade(): Damage.UpgradeValueBy(2m), EnergyCost.UpgradeBy(-1)  upgrade deltas

Our cards store upgrades as absolute values (_upgrades.py), the game as deltas;
both are turned into (base, upgraded) pairs and compared. Names differ too - we
call Juggernaut's number AMOUNT, the game JuggernautPower - so values are
paired by name where the names agree and by elimination where one number is
left on each side. Anything that still does not pair is listed for a person.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Server"))

from GameEngine.Registry.card_registry import create_card, known_card_ids
from GameEngine.Cards._card import Card
from GameEngine.Cards._card_ref import CardRef
from GameEngine.Cards._card_enums import CardClass

SOURCE = os.environ.get("STS2_SOURCE", r"D:\sts2_source")
CARDS_DIR = os.path.join(SOURCE, "MegaCrit.Sts2.Core.Models.Cards")
POOL = os.path.join(SOURCE, "MegaCrit.Sts2.Core.Models.CardPools", "IroncladCardPool.cs")

# The game's class name -> our card id, where snake_case does not get there.
ID_OVERRIDES = {"DefendIronclad": "defend", "StrikeIronclad": "strike", "FightMe": "fight_me",
                "ExpectAFight": "expect_a_fight"}

# DynamicVarSet's shorthand properties -> the key the var is stored under.
PROPERTY_KEYS = {"Vulnerable": "VulnerablePower", "Weak": "WeakPower",
                 "Strength": "StrengthPower", "Dexterity": "DexterityPower",
                 "Poison": "PoisonPower", "Doom": "DoomPower"}

# The game's TargetType -> ours.
TARGETS = {"AnyEnemy": "ENEMY", "AllEnemies": "ALL_ENEMIES", "Self": "SELF",
           "AnyAlly": "ALLY", "AllAllies": "ALL_ALLIES", "RandomEnemy": "RANDOM_ENEMY",
           "None": "SELF"}

KEYWORDS = {"Exhaust": "exhaust", "Ethereal": "ethereal", "Innate": "innate",
            "Retain": "retain", "Unplayable": "unplayable"}


def snake(name):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()


def block_after(text, header):
    """The brace-balanced body following `header`, or ''."""
    i = text.find(header)
    if i < 0:
        return ""
    i = text.find("{", i)
    depth, j = 0, i
    while j < len(text):
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        if depth == 0:
            return text[i + 1:j]
        j += 1
    return ""


def expression_after(text, header):
    """A `=> ...;` property body, or a braced one."""
    i = text.find(header)
    if i < 0:
        return ""
    semi = text.find(";", i)
    brace = text.find("{", i)
    if 0 <= brace < semi and "=>" not in text[i:brace]:
        return block_after(text, header)
    # arrays span lines: take up to the matching ');' of the expression
    depth, j = 0, text.find("=>", i)
    while j < len(text):
        ch = text[j]
        depth += {"(": 1, "{": 1, ")": -1, "}": -1}.get(ch, 0)
        if ch == ";" and depth <= 0:
            return text[i:j]
        j += 1
    return text[i:]


VAR = re.compile(r'new (\w+?)Var(?:<(\w+)>)?\(\s*(?:"(\w+)"\s*,\s*)?(-?\d+(?:\.\d+)?)m?')


def parse_game_card(cls):
    path = os.path.join(CARDS_DIR, cls + ".cs")
    text = open(path, encoding="utf-8").read()
    ctor = re.search(r"base\((-?\d+), CardType\.(\w+), CardRarity\.(\w+), TargetType\.(\w+)", text)
    cost = int(ctor.group(1))
    if "HasEnergyCostX => true" in text:
        cost = "X"
    card = {"class": cls, "cost": cost, "type": ctor.group(2), "rarity": ctor.group(3),
            "target": ctor.group(4), "vars": {}, "keywords": [], "upgrade": {},
            "upgrade_cost": 0, "upgrade_keywords": {}, "upgrade_other": []}

    for kind, generic, named, value in VAR.findall(expression_after(text, "CanonicalVars")):
        key = named or generic or kind
        card["vars"][key] = float(value) if "." in value else int(value)

    kw = expression_after(text, "CanonicalKeywords")
    card["keywords"] = sorted(set(re.findall(r"CardKeyword\.(\w+)", kw)))

    body = block_after(text, "protected override void OnUpgrade()")
    for line in [l.strip() for l in body.splitlines() if l.strip()]:
        m = re.search(r'DynamicVars(?:\.(\w+)|\["(\w+)"\])\.UpgradeValueBy\((-?\d+(?:\.\d+)?)m?\)', line)
        if m:
            key = m.group(2) or PROPERTY_KEYS.get(m.group(1), m.group(1))
            card["upgrade"][key] = card["upgrade"].get(key, 0) + float(m.group(3))
            continue
        m = re.search(r"EnergyCost\.UpgradeBy\((-?\d+)\)", line)
        if m:
            card["upgrade_cost"] += int(m.group(1))
            continue
        m = re.search(r"(Add|Remove)Keyword\(CardKeyword\.(\w+)\)", line)
        if m:
            card["upgrade_keywords"][m.group(2)] = m.group(1) == "Add"
            continue
        card["upgrade_other"].append(line)
    return card


def game_pool():
    text = open(POOL, encoding="utf-8").read()
    return re.findall(r"ModelDb\.Card<(\w+)>\(\)", block_after(text, "GenerateAllCards()"))


# --- our side ----------------------------------------------------------------

def our_values(card_id):
    """({CONST: (base, upgraded)}, cost, upgraded cost, keywords, upgraded keywords)."""
    plain, up = create_card(card_id), create_card(CardRef(card_id, upgraded=True))
    names = set()
    for klass in type(plain).__mro__:
        if klass in (Card, object):
            break
        names |= {k for k, v in vars(klass).items()
                  if k.isupper() and isinstance(v, (int, float)) and not isinstance(v, bool)}
    values = {k: (getattr(plain, k), getattr(up, k)) for k in sorted(names)}
    kw = lambda c: sorted(k for k, v in vars(c.properties).items() if v and k != "playable") + \
        ([] if c.properties.playable else ["unplayable"])
    return values, plain.cost, up.cost, kw(plain), kw(up)


def game_name_to_ours(key, cls):
    """Candidate constant names for a game var key, most likely first."""
    base = key[:-5] if key.endswith("Power") and key != "Power" else key
    out = [snake(base).upper()]
    aliases = {"CARDS": ["DRAW", "CARDS_DRAWN"], "HP_LOSS": ["HP", "SELF_DAMAGE", "LOSE_HP"],
               "ENERGY": ["ENERGY_GAIN"], "REPEAT": ["HITS", "TIMES"],
               "CALCULATION_BASE": ["DAMAGE", "BASE"], "CALCULATION_EXTRA": ["PER", "EXTRA", "BONUS"],
               "EXTRA_DAMAGE": ["EXTRA", "BONUS", "PER"], "MAX_HP": ["MAX_HP_GAIN"]}
    out += aliases.get(out[0], [])
    if key.endswith("Power") and snake(base).upper() == snake(cls).upper():
        out.append("AMOUNT")             # a power named after its own card
    return out


def compare(game, card_id):
    """Human-readable differences for one card."""
    diffs, loose = [], []
    ours, cost, up_cost, kws, up_kws = our_values(card_id)

    card = create_card(card_id)
    for field, mine, theirs in (
            ("type", card.card_type.name, game["type"].upper()),
            ("rarity", card.rarity.name, game["rarity"].upper()),
            ("target", card.target_type.name, TARGETS.get(game["target"], game["target"]))):
        if mine != theirs:
            diffs.append("%s %s -> %s" % (field, mine, theirs))

    g_cost = game["cost"]
    g_up_cost = g_cost if g_cost == "X" else g_cost + game["upgrade_cost"]
    if cost != g_cost:
        diffs.append("cost %s -> %s" % (cost, g_cost))
    if up_cost != g_up_cost:
        diffs.append("upgraded cost %s -> %s" % (up_cost, g_up_cost))

    g_kw = sorted(KEYWORDS.get(k, k.lower()) for k in game["keywords"])
    g_up_kw = set(g_kw)
    for k, on in game["upgrade_keywords"].items():
        (g_up_kw.add if on else g_up_kw.discard)(KEYWORDS.get(k, k.lower()))
    if kws != g_kw:
        diffs.append("keywords %s -> %s" % (kws or "-", g_kw or "-"))
    if up_kws != sorted(g_up_kw):
        diffs.append("upgraded keywords %s -> %s" % (up_kws or "-", sorted(g_up_kw) or "-"))

    g_vals = {k: (v, v + game["upgrade"].get(k, 0)) for k, v in game["vars"].items()}
    left_ours = dict(ours)
    left_game = {}
    for key, pair in g_vals.items():
        hit = next((n for n in game_name_to_ours(key, game["class"]) if n in left_ours), None)
        if hit is None:
            left_game[key] = pair
            continue
        mine = left_ours.pop(hit)
        if tuple(mine) != tuple(pair):
            diffs.append("%s %s/%s -> %s/%s  (game: %s)" % (hit, *fmt(mine), *fmt(pair), key))
    # one number left on each side: they are the same number under two names
    if len(left_game) == 1 and len(left_ours) == 1:
        (key, pair), (hit, mine) = left_game.popitem(), left_ours.popitem()
        if tuple(mine) != tuple(pair):
            diffs.append("%s %s/%s -> %s/%s  (game: %s)" % (hit, *fmt(mine), *fmt(pair), key))
    for key, pair in left_game.items():
        loose.append("game has %s %s/%s, not matched to any of ours" % (key, *fmt(pair)))
    for hit, mine in left_ours.items():
        loose.append("ours has %s %s/%s, not matched in the game" % (hit, *fmt(mine)))
    for line in game["upgrade_other"]:
        loose.append("game upgrade also does: " + line)
    return diffs, loose


def fmt(pair):
    return tuple(int(x) if isinstance(x, float) and x.is_integer() else x for x in pair)


def main(argv):
    if not os.path.isdir(CARDS_DIR):
        print("no decompiled source at %s - see the docstring" % SOURCE)
        return 2
    pool = game_pool()
    ours_ids = set(known_card_ids())
    our_ironclad = {i for i in ours_ids if create_card(i).card_class is CardClass.IRONCLAD}

    games, changed, clean, missing, notes = {}, {}, [], [], {}
    for cls in pool:
        game = parse_game_card(cls)
        games[cls] = game
        card_id = ID_OVERRIDES.get(cls, snake(cls))
        if card_id not in ours_ids:
            missing.append((cls, card_id))
            continue
        our_ironclad.discard(card_id)
        diffs, loose = compare(game, card_id)
        if diffs:
            changed[card_id] = diffs
        else:
            clean.append(card_id)
        if loose:
            notes[card_id] = loose

    print("game v%s Ironclad pool: %d cards" % (game_version(), len(pool)))
    print()
    print("== %d cards differ from the game ==" % len(changed))
    for card_id, diffs in sorted(changed.items()):
        print("  %-18s %s" % (card_id, diffs[0]))
        for d in diffs[1:]:
            print("  %-18s %s" % ("", d))
    print()
    print("== in the game's Ironclad pool, not in ours (%d) ==" % len(missing))
    for cls, card_id in missing:
        print("  %s (would be %s)" % (cls, card_id))
    print()
    print("== Ironclad in ours, not in the game (%d) ==" % len(our_ironclad))
    for card_id in sorted(our_ironclad):
        print("  " + card_id)
    print()
    print("== could not pair automatically - read these (%d cards) ==" % len(notes))
    for card_id, loose in sorted(notes.items()):
        for line in loose:
            print("  %-18s %s" % (card_id, line))
    print()
    print("match exactly: %d   differ: %d   missing: %d   extra: %d"
          % (len(clean), len(changed), len(missing), len(our_ironclad)))

    if "--json" in argv:
        out = argv[argv.index("--json") + 1]
        with open(out, "w", encoding="utf-8") as handle:
            json.dump({"version": game_version(), "cards": games}, handle, indent=1, sort_keys=True)
        print("game values written to", out)
    return 0


def game_version():
    info = os.path.join(os.path.dirname(SOURCE.rstrip("\\/")), "SteamLibrary", "steamapps",
                        "common", "Slay the Spire 2", "release_info.json")
    for path in (info, r"D:\SteamLibrary\steamapps\common\Slay the Spire 2\release_info.json"):
        if os.path.exists(path):
            return json.load(open(path, encoding="utf-8")).get("version", "?").lstrip("v")
    return "?"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
