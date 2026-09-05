# -*- coding: utf-8 -*-
"""Load and validate config.json -- the setup play.py reads instead of hardcoding a party, a deck..."""

import io
import json
import os

DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")


DEFAULTS = {
    "preset": None,
    "party": [
        {"name": "Ironclad", "hp": 80, "energy": 3,
         "deck": "starter", "starting_relic": "Burning Blood"},
    ],
    "content": {
        "relics": True,
        "potions": True,
        "card_rewards": True,
        "relic_rewards": True,
        "potion_rewards": True,
    },
    "cards": {
        "allow": None,
        "deny": [],
    },
    "mode": "ask",
    "encounter": None,
    "seed": None,

    "simple": {
        "players": 1,
        "player_hp": 30,
        "energy": 3,
        "enemy_hp": 75,
        "enemy_damage": 11,
        "max_turns": 50,
        "scale_enemy": None,
    },
}


PRESETS = {
    "full": {},
    "basic": {
        "party": [{"name": "Ironclad", "hp": 30, "energy": 3,
                   "deck": "strike_defend", "starting_relic": None}],
        "content": {"relics": False, "potions": False, "card_rewards": False,
                    "relic_rewards": False, "potion_rewards": False},
        "cards": {"allow": ["Strike", "Defend"], "deny": []},
        "mode": "single",
        "encounter": "1",
    },
    "coop": {
        "party": [
            {"name": "Ironclad", "hp": 80, "energy": 3, "deck": "starter",
             "starting_relic": "Burning Blood"},
            {"name": "Vanguard", "hp": 65, "energy": 3, "deck": "coop_support",
             "starting_relic": None},
            {"name": "Rearguard", "hp": 65, "energy": 3, "deck": "coop_support",
             "starting_relic": None},
        ],
        "simple": {"players": 3},
    },
    "no_items": {
        "content": {"relics": False, "potions": False, "card_rewards": True,
                    "relic_rewards": False, "potion_rewards": False},
    },
}

DECKS = ("starter", "coop_support", "strike_defend")
MODES = ("ask", "gauntlet", "single")


class ConfigError(Exception):
    """Raised for a config a human needs to fix. The message names the key."""


def _merge(base, override):
    """Recursive dict merge -- an override supplies only what it changes."""
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load(path=None, quiet=False):
    """Read a config, apply its preset, fill in defaults, validate."""
    path = path or DEFAULT_PATH
    if not os.path.exists(path):
        if not quiet:
            print("  (no {} -- using the full game)".format(
                os.path.basename(path)))
        return dict(DEFAULTS)

    try:
        raw = json.loads(io.open(path, encoding="utf-8").read())
    except ValueError as exc:
        raise ConfigError("{} is not valid JSON: {}".format(path, exc))
    if not isinstance(raw, dict):
        raise ConfigError("{} must contain a JSON object".format(path))

    preset_name = raw.get("preset")
    if preset_name is not None:
        if preset_name not in PRESETS:
            raise ConfigError(
                "preset {!r} is not one of {}".format(
                    preset_name, ", ".join(sorted(PRESETS))))
        cfg = _merge(DEFAULTS, PRESETS[preset_name])
    else:
        cfg = dict(DEFAULTS)

    cfg = _merge(cfg, raw)
    validate(cfg)
    return cfg


def validate(cfg):
    """Fail loudly, naming the key, rather than half-starting a broken game."""
    unknown = set(cfg) - set(DEFAULTS)
    if unknown:
        raise ConfigError("unknown top-level key(s): {}".format(
            ", ".join(sorted(unknown))))

    party = cfg.get("party")
    if not isinstance(party, list) or not party:
        raise ConfigError("party must be a non-empty list")
    if len(party) > 4:
        raise ConfigError(
            "party has {} members; the engine supports 1-4".format(len(party)))
    for i, member in enumerate(party):
        where = "party[{}]".format(i)
        if not isinstance(member, dict):
            raise ConfigError(where + " must be an object")
        for key in ("hp", "energy"):
            v = member.get(key, DEFAULTS["party"][0][key])
            if not isinstance(v, int) or v < 1:
                raise ConfigError("{}.{} must be a positive integer, got {!r}"
                                  .format(where, key, v))
        deck = member.get("deck", "starter")
        if deck not in DECKS and not isinstance(deck, list):
            raise ConfigError(
                "{}.deck must be one of {} or a list of card names, got {!r}"
                .format(where, ", ".join(DECKS), deck))

    if cfg.get("mode") not in MODES:
        raise ConfigError("mode must be one of {}, got {!r}".format(
            ", ".join(MODES), cfg.get("mode")))

    for key in ("relics", "potions", "card_rewards", "relic_rewards",
                "potion_rewards"):
        v = cfg["content"].get(key)
        if not isinstance(v, bool):
            raise ConfigError("content.{} must be true or false, got {!r}"
                              .format(key, v))

    allow = cfg["cards"].get("allow")
    if allow is not None and (not isinstance(allow, list) or not allow):
        raise ConfigError("cards.allow must be null or a non-empty list")
    if not isinstance(cfg["cards"].get("deny"), list):
        raise ConfigError("cards.deny must be a list")

    seed = cfg.get("seed")
    if seed is not None and not isinstance(seed, int):
        raise ConfigError("seed must be null or an integer, got {!r}".format(seed))

    simple = cfg.get("simple", {})
    if not isinstance(simple, dict):
        raise ConfigError("simple must be an object")
    unknown = set(simple) - set(DEFAULTS["simple"])
    if unknown:
        raise ConfigError("unknown simple key(s): {}".format(
            ", ".join(sorted(unknown))))
    n = simple.get("players", 1)
    if not isinstance(n, int) or not 1 <= n <= 4:
        raise ConfigError(
            "simple.players must be an integer 1-4, got {!r}".format(n))
    for key in ("player_hp", "energy", "enemy_hp", "enemy_damage", "max_turns"):
        v = simple.get(key, DEFAULTS["simple"][key])
        if not isinstance(v, int) or v < 1:
            raise ConfigError("simple.{} must be a positive integer, got {!r}"
                              .format(key, v))
    scale = simple.get("scale_enemy")
    if scale is not None and not isinstance(scale, bool):
        raise ConfigError(
            "simple.scale_enemy must be true, false or null, got {!r}".format(scale))
    return cfg


def simple_kwargs(cfg):
    """The `simple` section as keyword arguments for battle() / SimpleEnv() / play_interactive(), which..."""
    s = dict(DEFAULTS["simple"])
    s.update(cfg.get("simple", {}))
    return s


def card_filter(cfg):
    """A predicate over card NAMES, honouring allow and deny."""
    allow = cfg["cards"].get("allow")
    deny = set(cfg["cards"].get("deny") or ())

    def permitted(name):
        if name in deny:
            return False
        return allow is None or name in allow

    return permitted


def build_deck(spec, permitted):
    """Turn a deck spec into real Cards, then apply the card filter."""
    from game_engine.cards import (make_starter_deck, make_coop_support_deck,
                                   CARD_POOL_IRONCLAD, ANCIENT_CARDS_IRONCLAD,
                                   COLORLESS_POOL, ANCIENT_COLORLESS)
    if spec == "starter":
        deck = make_starter_deck()
    elif spec == "coop_support":
        deck = make_coop_support_deck()
    elif spec == "strike_defend":
        deck = [c for c in make_starter_deck() if c.name in ("Strike", "Defend")]
    else:
        by_name = {}
        for c in make_starter_deck() + make_coop_support_deck():
            by_name.setdefault(c.name, lambda c=c: c.clone())
        for pool in (CARD_POOL_IRONCLAD, ANCIENT_CARDS_IRONCLAD,
                     COLORLESS_POOL, ANCIENT_COLORLESS):
            for f in pool:
                by_name.setdefault(f().name, f)
        deck = []
        for name in spec:
            if name not in by_name:
                raise ConfigError("no card named {!r}".format(name))
            deck.append(by_name[name]())
    kept = [c for c in deck if permitted(c.name)]
    if not kept:
        raise ConfigError(
            "the card filter removed every card from deck {!r} -- check "
            "cards.allow / cards.deny".format(spec))
    return kept


def build_party(cfg):
    """The Players a config describes, relics included (or not)."""
    from game_engine.entities import Player
    from game_engine.relics import BURNING_BLOOD, RELIC_POOL_IRONCLAD

    by_relic_name = {r.name: r for r in RELIC_POOL_IRONCLAD}
    by_relic_name[BURNING_BLOOD.name] = BURNING_BLOOD
    permitted = card_filter(cfg)

    players = []
    for i, member in enumerate(cfg["party"]):
        defaults = DEFAULTS["party"][0]
        name = member.get("name") or "Player {}".format(i + 1)
        deck = build_deck(member.get("deck", "starter"), permitted)
        p = Player(name,
                   max_hp=member.get("hp", defaults["hp"]),
                   max_energy=member.get("energy", defaults["energy"]),
                   deck=deck)
        relic_name = member.get("starting_relic")
        if cfg["content"]["relics"] and relic_name:
            if relic_name not in by_relic_name:
                raise ConfigError("no relic named {!r}".format(relic_name))
            p.add_relic(by_relic_name[relic_name])
        players.append(p)
    return players


def describe(cfg):
    """One short block shown at startup, so what is switched off is visible rather than something the..."""
    lines = []
    preset = cfg.get("preset")
    lines.append("Setup: {}".format(preset if preset else "custom"))
    party = ", ".join("{} ({} hp, {} energy)".format(
        m.get("name", "?"), m.get("hp", 80), m.get("energy", 3))
        for m in cfg["party"])
    lines.append("  party    : " + party)
    allow = cfg["cards"].get("allow")
    lines.append("  cards    : " + ("all" if allow is None
                                    else ", ".join(allow)))
    off = [k for k, v in sorted(cfg["content"].items()) if not v]
    lines.append("  disabled : " + (", ".join(off) if off else "nothing"))
    if cfg.get("seed") is not None:
        lines.append("  seed     : {}".format(cfg["seed"]))
    return "\n".join(lines)
