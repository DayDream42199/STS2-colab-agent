"""Each teammate style's usual profile, for the swapped-profile test (Advantage_point).

reference_profiles() plays teams of one teammate of each style next to a fixed
agent (the Cheese bot in seat 0) and averages the teammate's A, S, T at the end
of each team. farthest() names the style whose profile is furthest from a given
style's: in the swapped test the agent is shown that one instead.
"""
import dataclasses
import hashlib
import json
import math
import os

from .bots import CheeseBot
from .config import A_END, A_PLAY0, A_CHOOSE0, A_STOP, N_TARGETS, EnvConfig

STYLES = EnvConfig.teammate_types                    # the named styles; a blend bot has no usual profile


def cheese_action(env, bot):
    """The Cheese bot playing the agent's seat through the env's actions."""
    m = env.action_masks()
    if env.dc is not None:
        return A_STOP if m[A_STOP] else A_CHOOSE0
    a = bot.act(env.combat, 0)
    return A_END if a[0] == "end" else A_PLAY0 + N_TARGETS * a[1] + env.target_slot(a[2])


def reference_profiles(cfg, teams=3, seed=4242):
    """{style: {A, S, T}}, averaged over `teams` teams of cfg.team_fights fights each."""
    from .env import CollabEnv                       # here: env imports this module
    refs = {}
    for style in STYLES:
        env = CollabEnv(dataclasses.replace(cfg, swap_profiles=False, history_fights=0), seed=seed, fixed_team=[style])
        bot = CheeseBot()
        found = []
        env.reset()
        while len(found) < teams:
            _, _, done, _, _ = env.step(cheese_action(env, bot))
            if done:
                if env.fights_left <= 0:             # the team's last fight: its profile is final
                    found.append(dict(env.team_profiles.get(1)))
                env.reset()
        refs[style] = {k: sum(p[k] for p in found) / len(found) for k in ("A", "S", "T")}
    return refs


def load_or_make(cfg, path=None):
    """The reference profiles saved at `path` (default: runs/style_profiles.json, or on the real
    engine runs/style_profiles_real.json, with its own file per deck and fight mix, and for
    no_wait, blind_teammates and start_hp: a style's usual profile depends on them), worked out and saved there the first time."""
    if path is None:
        path = "runs/style_profiles.json"
        if cfg.engine == "real":
            path = "runs/style_profiles_real.json"
            weights = tuple(cfg.real_pool_weights)
            if cfg.real_deck or cfg.real_extra_cards != EnvConfig.real_extra_cards or weights != EnvConfig.real_pool_weights:
                key = repr((tuple(cfg.real_deck or ()), cfg.real_extra_cards, weights)).encode()
                path = f"runs/style_profiles_real_{hashlib.md5(key).hexdigest()[:8]}.json"
            path = path.replace(".json", "_v2.json")   # v2: the bots see Lift's Block, so they play differently
        if cfg.no_wait or cfg.blind_teammates:      # teammates never act first, so their profiles read differently
            path = path.replace(".json", "_nowait.json")
        if cfg.start_hp:
            path = path.replace(".json", "_hp" + "-".join(f"{share * 100:g}" for share in cfg.start_hp) + ".json")
    if os.path.exists(path):
        with open(path) as f:
            refs = json.load(f)
        if set(STYLES) <= set(refs):
            return refs
    refs = reference_profiles(cfg)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(refs, f, indent=2)
    return refs


def farthest(style, refs):
    """The other style whose A, S, T are furthest from `style`'s."""
    me = refs[style]
    return max((s for s in refs if s != style),
               key=lambda s: math.dist([me[k] for k in "AST"], [refs[s][k] for k in "AST"]))


def farthest_from(profile, refs):
    """The style whose A, S, T are furthest from this profile (a blend bot has no style of its own)."""
    return max(refs, key=lambda s: math.dist([profile[k] for k in "AST"], [refs[s][k] for k in "AST"]))
