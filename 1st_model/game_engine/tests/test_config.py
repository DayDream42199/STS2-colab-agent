# -*- coding: utf-8 -*-
"""config.json actually restricts what it says it restricts."""
import io
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from testing import config
from game_engine.cards import CARD_POOL_IRONCLAD

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  [{'ok' if ok else 'FAIL'}] {label}: got {got!r}, want {want!r}")
    if not ok:
        FAILS.append(label)


def write(d):
    """Write a config dict to a temp file and load it back."""
    path = os.path.join(tempfile.gettempdir(), "sts2_test_config.json")
    io.open(path, "w", encoding="utf-8").write(json.dumps(d))
    return config.load(path, quiet=True)


def expect_error(label, d):
    """A bad config must raise ConfigError, not crash somewhere downstream."""
    try:
        cfg = write(d)
        config.build_party(cfg)
    except config.ConfigError as exc:
        print(f"  [ok] {label}: {exc}")
        return
    except Exception as exc:
        print(f"  [FAIL] {label}: raised {type(exc).__name__}, not ConfigError")
        FAILS.append(label)
        return
    print(f"  [FAIL] {label}: accepted a config it should have rejected")
    FAILS.append(label)


print("1. the repo's own config.json is valid; an EMPTY one means 'full game'")
shipped = config.load(os.path.join(ROOT, "config.json"), quiet=True)
check("config.json parses and validates", isinstance(shipped, dict), True)
bare = write({})
check("an empty config switches nothing off",
      sorted(k for k, v in bare["content"].items() if not v), [])
check("...and allows every card", bare["cards"]["allow"], None)

print()
print("2. a missing file is not an error -- it means the full game")
missing = config.load(os.path.join(tempfile.gettempdir(), "definitely_absent.json"),
                      quiet=True)
check("missing config falls back to defaults", missing, dict(config.DEFAULTS))

print()
print("3. presets apply")
basic = write({"preset": "basic"})
check("basic allows only Strike and Defend",
      sorted(basic["cards"]["allow"]), ["Defend", "Strike"])
check("basic switches off every content flag",
      sorted(k for k, v in basic["content"].items() if v), [])
check("basic starts a single fight", basic["mode"], "single")

print()
print("4. explicit keys override the preset")
mixed = write({"preset": "basic", "party": [{"name": "Tank", "hp": 99}]})
check("overridden hp wins", mixed["party"][0]["hp"], 99)
check("...but the preset's card filter survives",
      sorted(mixed["cards"]["allow"]), ["Defend", "Strike"])

print()
print("5. the restrictions BIND, not just parse")
party = config.build_party(basic)
p = party[0]
check("deck holds only permitted cards",
      sorted({c.name for c in p.deck_template}), ["Defend", "Strike"])
check("no starting relic when relics are off", [r.name for r in p.relics], [])
check("party hp comes from the config", p.max_hp, 30)

permitted = config.card_filter(basic)
leaked = [f().name for f in CARD_POOL_IRONCLAD if permitted(f().name)]
check("the filter empties the reward pool too", leaked, [])

denied = write({"cards": {"allow": None, "deny": ["Bash"]}})
p2 = config.build_party(denied)[0]
check("deny removes Bash from the starter deck",
      "Bash" in {c.name for c in p2.deck_template}, False)
check("...while leaving the rest",
      sorted({c.name for c in p2.deck_template}), ["Defend", "Strike"])

print()
print("6. relics stay on when the config says so")
withrelic = write({"party": [{"name": "I", "starting_relic": "Burning Blood"}]})
check("Burning Blood is granted",
      [r.name for r in config.build_party(withrelic)[0].relics], ["Burning Blood"])

print()
print("7. decks: named, explicit, and co-op")
custom = write({"party": [{"name": "C", "deck": ["Strike", "Bash", "Anger"]}]})
check("an explicit card list builds exactly that deck",
      [c.name for c in config.build_party(custom)[0].deck_template],
      ["Strike", "Bash", "Anger"])
coop = write({"party": [{"name": "A"}, {"name": "B", "deck": "coop_support"},
                        {"name": "C", "deck": "strike_defend"}]})
check("a 3-player party builds 3 players", len(config.build_party(coop)), 3)

print()
print("8. bad configs fail with a message naming the problem")
expect_error("unknown top-level key", {"partyy": []})
expect_error("empty party", {"party": []})
expect_error("party of 5", {"party": [{"name": str(i)} for i in range(5)]})
expect_error("negative hp", {"party": [{"name": "X", "hp": -3}]})
expect_error("bad mode", {"mode": "sideways"})
expect_error("non-boolean content flag", {"content": {"relics": "yes"}})
expect_error("unknown preset", {"preset": "hardcore"})
expect_error("unknown card name", {"party": [{"name": "X", "deck": ["Nonexistent"]}]})
expect_error("unknown relic name", {"party": [{"name": "X", "starting_relic": "Nope"}]})
expect_error("filter removes every card",
             {"cards": {"allow": ["Nonexistent"], "deny": []}})
expect_error("non-integer seed", {"seed": "zero"})

path = os.path.join(tempfile.gettempdir(), "sts2_bad.json")
io.open(path, "w", encoding="utf-8").write("{not json")
try:
    config.load(path, quiet=True)
    check("malformed JSON is rejected", "accepted", "ConfigError")
except config.ConfigError as exc:
    print(f"  [ok] malformed JSON: {exc}")

print()
print("9. describe() names what is switched off")
text = config.describe(basic)
check("describe mentions the disabled content", "relics" in text, True)
check("describe lists the allowed cards", "Strike" in text, True)

print()
print("10. the `simple` section (simple.py's cut-down game)")
kw = config.simple_kwargs(write({}))
check("defaults are solo", kw["players"], 1)
check("scale_enemy defaults to null (= auto)", kw["scale_enemy"], None)

shipped_kw = config.simple_kwargs(shipped)
check("whatever config.json asks for is a usable party size",
      1 <= shipped_kw["players"] <= 4, True)

coop = write({"simple": {"players": 3, "enemy_hp": 200, "scale_enemy": False}})
kw = config.simple_kwargs(coop)
check("a co-op simple setup round-trips",
      (kw["players"], kw["enemy_hp"], kw["scale_enemy"]), (3, 200, False))
check("unspecified simple keys keep their defaults", kw["player_hp"], 30)

from testing.simple import battle, greedy, SimpleEnv
r = battle(greedy, seed=1, **kw)
check("the kwargs drive a real 3-player fight", len(r.party_hp), 3)

env = SimpleEnv(**{k: v for k, v in kw.items() if k != "max_turns"})
env.reset()
check("SimpleEnv takes the same kwargs", env.n_players, 3)
check("...and its observation grows with the party",
      len(env.reset()), 7 + 2 * (3 - 1))

solo = SimpleEnv()
check("solo observation is still 7 floats (saved agents keep working)",
      len(solo.reset()), 7)

check("the coop preset exists", "coop" in config.PRESETS, True)
cp = write({"preset": "coop"})
check("coop preset builds 3 players", len(config.build_party(cp)), 3)

expect_error("simple.players out of range", {"simple": {"players": 9}})
expect_error("negative simple.enemy_hp", {"simple": {"enemy_hp": -5}})
expect_error("non-boolean scale_enemy", {"simple": {"scale_enemy": "yes"}})
expect_error("unknown simple key", {"simple": {"nonsense": 1}})


print()
if FAILS:
    print(f"FAILURE: {len(FAILS)} check(s) failed")
    for f in FAILS:
        print("  - " + f)
    sys.exit(1)
print("all config checks passed")
