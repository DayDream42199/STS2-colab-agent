# -*- coding: utf-8 -*-
"""#43 + #44: env.py must agree with the engine it wraps."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import numpy as np
from game_engine.entities import Player
import game_engine.enemies as E
from game_engine.combat import CombatEngine
import game_engine.cards as C
from game_engine.cards import CardType, TargetMode, make_starter_deck
from game_engine.statuses import StatusType
import game_engine.env as ENV

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  [{'ok' if ok else 'FAIL'}] {label}: got {got!r}, want {want!r}")
    if not ok:
        FAILS.append(label)


def bag(hp=4000):
    e = E.make_nibbit()
    e.max_hp = e.hp = hp
    return e


def make_env(deck=None, players=1, energy=99):
    def mk_players():
        return [Player(f"P{i}", 200, energy, deck=deck or make_starter_deck())
                for i in range(players)]
    e = ENV.CombatEnv(mk_players, lambda: [bag()], seed=5)
    e.reset()
    for p in e.engine.players:
        p.energy = energy
    return e


def pool(name):
    for f in (list(C.COLORLESS_POOL) + list(C.ANCIENT_COLORLESS)
              + list(C.CURSE_POOL) + list(C.CARD_POOL_IRONCLAD)):
        c = f()
        if c.name == name:
            return c
    for mk in C.STATUS_CARDS:
        c = mk()
        if c.name == name:
            return c
    raise KeyError(name)


def mask_legal_slots(e):
    """Hand slots the mask says are playable against at least one target."""
    m = e.legal_action_mask()
    out = set()
    p = e._current_player()
    for slot in range(min(len(p.hand), ENV.MAX_HAND)):
        enemy_base = slot * ENV.MAX_ENEMIES
        ally_base = ENV.FIRST_CARD_ALLY_ACTION + slot * ENV.MAX_ALLY_TARGETS
        if (any(m[enemy_base + t] > 0 for t in range(ENV.MAX_ENEMIES))
                or any(m[ally_base + t] > 0
                       for t in range(ENV.MAX_ALLY_TARGETS))):
            out.add(slot)
    return out


def engine_legal_slots(e):
    p = e._current_player()
    playable = {id(c) for c in e.engine.playable_cards(p)}
    return {slot for slot, c in enumerate(p.hand[:ENV.MAX_HAND])
            if id(c) in playable}


def agree(label, e):
    """The core property: the mask and the engine name the same slots."""
    m, g = mask_legal_slots(e), engine_legal_slots(e)
    check(label, sorted(m), sorted(g))
    return m, g


print("=" * 74)
print("The gates that were only ever checked inside play_card")
print("=" * 74)

e = make_env()
p = e._current_player()
p.hand = [make_starter_deck()[0] for _ in range(3)]
p.add_status(StatusType.RINGING, 1)
agree("Ringing, before any card is played", e)
e.engine.play_card(p, p.hand[0], target=e.engine.enemies[0])
m, g = agree("Ringing, after the 1 allowed card", e)
check("...and nothing is legal any more", sorted(m), [])

e = make_env()
p = e._current_player()
p.hand = [c for c in make_starter_deck() if c.name == "Defend"][:2]
p.hand += [make_starter_deck()[0]]
p.add_status(StatusType.SMOGGY, 1)
agree("Smoggy, before any Skill", e)
e.engine.play_card(p, p.hand[0])
m, g = agree("Smoggy, after 1 Skill", e)
check("...the remaining Skill is blocked, the Attack is not",
      sorted(m), [1])

e = make_env()
p = e._current_player()
p.hand = [make_starter_deck()[0] for _ in range(3)]
for c in p.hand:
    c.bound = True
agree("Bound, before any Bound card", e)
e.engine.play_card(p, p.hand[0], target=e.engine.enemies[0])
m, g = agree("Bound, after one Bound card", e)
check("...no further Bound card is legal", sorted(m), [])

print()
print("=" * 74)
print("The gates added by the Colorless port")
print("=" * 74)

e = make_env()
p = e._current_player()
p.hand = [pool("Clash"), [c for c in make_starter_deck() if c.name == "Defend"][0]]
m, g = agree("Clash with a non-Attack in hand", e)
check("...Clash itself is not offered", 0 in m, False)
p.hand = [pool("Clash"), make_starter_deck()[0]]
m, g = agree("Clash with an all-Attack hand", e)
check("...Clash is offered", 0 in m, True)

e = make_env()
p = e._current_player()
p.hand = [pool("Sloth")] + [make_starter_deck()[0] for _ in range(4)]
for _ in range(3):
    playable = e.engine.playable_cards(p)
    e.engine.play_card(p, playable[0], target=e.engine.enemies[0])
m, g = agree("Sloth after 3 plays", e)
check("...the cap leaves nothing legal", sorted(m), [])

e = make_env()
p = e._current_player()
p.hand = [make_starter_deck()[0], pool("Enthralled")]
m, g = agree("Enthralled held in hand", e)
check("...only Enthralled is offered", sorted(m), [1])

e = make_env()
p = e._current_player()
p.hand = [C.make_wound(), pool("Injury"), make_starter_deck()[0]]
p.energy = 9999
m, g = agree("unplayables with 9999 energy", e)
check("...only the real card is offered", sorted(m), [2])

print()
print("=" * 74)
print("Energy, X-cost and empty hands")
print("=" * 74)

e = make_env(energy=0)
p = e._current_player()
p.hand = [make_starter_deck()[0], make_starter_deck()[1]]
p.energy = 0
m, g = agree("no energy", e)
check("...nothing but end-turn", sorted(m), [])
check("end turn is always legal", e.legal_action_mask()[ENV.END_TURN_ACTION], 1.0)

e = make_env()
p = e._current_player()
p.hand = [pool("Volley")]
p.energy = 0
m, g = agree("X-cost card at 0 energy", e)
check("...still legal (allowed, just useless)", sorted(m), [0])

e = make_env()
p = e._current_player()
p.hand = []
agree("empty hand", e)
check("empty hand still allows end turn",
      e.legal_action_mask()[ENV.END_TURN_ACTION], 1.0)

print()
print("=" * 74)
print("Property sweep: every pool card, in every gate state")
print("=" * 74)
disagreements = []
states = [
    ("clean", lambda p: None),
    ("ringing spent", lambda p: (p.add_status(StatusType.RINGING, 1),
                                 setattr(p, "cards_played_this_turn", 1))),
    ("smoggy spent", lambda p: (p.add_status(StatusType.SMOGGY, 1),
                                setattr(p, "skills_played_this_turn", 1))),
    ("low energy", lambda p: setattr(p, "energy", 1)),
    ("sloth capped", lambda p: (p.hand.append(pool("Sloth")),
                                setattr(p, "cards_played_this_turn", 3))),
]
every = (list(C.COLORLESS_POOL) + list(C.ANCIENT_COLORLESS)
         + list(C.CARD_POOL_IRONCLAD))
for state_name, apply_state in states:
    for factory in every:
        e = make_env()
        p = e._current_player()
        p.hand = [factory()]
        apply_state(p)
        m, g = mask_legal_slots(e), engine_legal_slots(e)
        if m != g:
            disagreements.append(f"{factory().name} [{state_name}]: mask={m} engine={g}")
check(f"mask == engine for {len(every)} cards x {len(states)} states",
      disagreements, [])

print()
print("=" * 74)
print("End to end: a masked agent never eats the illegal-action penalty")
print("=" * 74)
rng = np.random.default_rng(0)
penalties = 0
steps = 0
for seed in range(30):
    def mk_players():
        deck = make_starter_deck()
        deck += [C.make_wound(), pool("Injury"), pool("Clash"), pool("Sloth")]
        return [Player("P", 80, 3, deck=deck)]
    e = ENV.CombatEnv(mk_players, lambda: [E.make_nibbit()], seed=seed)
    e.reset()
    done = False
    guard = 0
    while not done and guard < 400:
        guard += 1
        mask = e.legal_action_mask()
        legal = np.flatnonzero(mask > 0)
        action = int(rng.choice(legal))
        _, reward, done, _ = e.step(action)
        steps += 1
        if reward <= -1.0 and not done:
            penalties += 1
check(f"illegal-action penalties across {steps} masked random steps",
      penalties, 0)

print()
print("=" * 74)
print("Observation layout and the board cap (#44)")
print("=" * 74)

check("env MAX_ENEMIES tracks the engine's board cap",
      ENV.MAX_ENEMIES, CombatEngine.MAX_ENEMIES)

for n in (1, 2, 3, 4):
    e = ENV.CombatEnv(
        lambda n=n: [Player(f"P{i}", 80, 3, deck=make_starter_deck())
                     for i in range(n)],
        lambda: [bag()], seed=1)
    obs = e.reset()
    check(f"observation is a fixed {ENV.OBS_SIZE} floats at {n} player(s)",
          len(obs), e.observation_space_size())

e = ENV.CombatEnv(
    lambda: [Player(f"P{i}", 80, 3, deck=make_starter_deck()) for i in range(3)],
    lambda: [bag()], seed=1)
e.reset()
for p in e.engine.players:
    p.hp = p.max_hp
enemy = e.engine.enemies[0]
enemy.hp = enemy.max_hp // 4
obs = e._observe()
check("3 players: enemy 0 sits at the enemy offset, not shifted into it",
      round(float(obs[ENV.OBS_OFFSETS["enemies"][0]]), 2), 0.25)
p4 = ENV.OBS_OFFSETS["players"][0] + 3 * ENV.ENTITY_FEATURES
check("...and the unused 4th player slot is zeroed",
      [float(x) for x in obs[p4:p4 + ENV.ENTITY_FEATURES]] == [0.0] * ENV.ENTITY_FEATURES,
      True)

e = ENV.CombatEnv(lambda: [Player("P", 200, 99, deck=make_starter_deck())],
                  lambda: [E.make_phrog_parasite()], seed=3)
e.reset()
eng = e.engine
eng.enemies[0].hp = 1
p = e._current_player()
p.energy = 99
p.hand = [make_starter_deck()[0]]
eng.play_card(p, p.hand[0], target=eng.enemies[0])
alive_idx = [i for i, en in enumerate(eng.enemies) if en.alive]
check("Phrog Parasite's death spawns past the old 4-enemy cap",
      len(eng.enemies) > 4, True)
p.hand = [make_starter_deck()[0]]
m = e.legal_action_mask()
targetable = sorted({t for t in range(ENV.MAX_ENEMIES)
                     if m[0 * ENV.MAX_ENEMIES + t] > 0})
check("every living enemy is targetable", targetable, alive_idx)
obs = e._observe()
e_off = ENV.OBS_OFFSETS["enemies"][0]
live_slots = [i for i in range(ENV.MAX_ENEMIES)
              if obs[e_off + i * ENV.ENTITY_FEATURES] > 0]
check("...and every living enemy is visible in the observation",
      live_slots, alive_idx)

check("action space covers both card axes and end-turn",
      e.action_space_size(),
      ENV.CARD_ENEMY_ACTIONS + ENV.CARD_ALLY_ACTIONS + 1)
check("the enemy and player card axes do not overlap",
      (ENV.FIRST_CARD_ALLY_ACTION, ENV.END_TURN_ACTION),
      (ENV.CARD_ENEMY_ACTIONS,
       ENV.CARD_ENEMY_ACTIONS + ENV.CARD_ALLY_ACTIONS))
check("potions are out of the action space entirely",
      hasattr(ENV, "FIRST_POTION_ACTION"), False)

print()
print("=" * 74)
print("The hand is visible in the observation (#48)")
print("=" * 74)

HAND_OFF = ENV.OBS_OFFSETS["hand"][0]
F = ENV.HAND_FEATURES
IDX = {name: i for i, name in enumerate(ENV.HAND_FEATURE_NAMES)}


def slot_feats(obs, slot):
    return [float(x) for x in obs[HAND_OFF + slot * F: HAND_OFF + (slot + 1) * F]]


def feat(obs, slot, name):
    return slot_feats(obs, slot)[IDX[name]]


e = make_env()
p = e._current_player()
check("observation_space_size matches the vector", len(e._observe()),
      e.observation_space_size())

p.hand = [make_starter_deck()[0]]
o_strike = e._observe().copy()
p.hand = [C.make_wound()]
o_wound = e._observe().copy()
check("swapping the hand changes the observation",
      np.array_equal(o_strike, o_wound), False)

strike = make_starter_deck()[0]
defend = [c for c in make_starter_deck() if c.name == "Defend"][0]
p.hand = [strike, defend]
p.energy = 99
obs = e._observe()
check("slot 0 is the Attack", feat(obs, 0, "is_attack"), 1.0)
check("slot 0 is not a Skill", feat(obs, 0, "is_skill"), 0.0)
check("slot 1 is the Skill", feat(obs, 1, "is_skill"), 1.0)
check("slot 1 is not an Attack", feat(obs, 1, "is_attack"), 0.0)
check("empty slot 2 is all zeros", slot_feats(obs, 2) == [0.0] * F, True)
check("occupied flag set on slot 0", feat(obs, 0, "occupied"), 1.0)
check("occupied flag clear on slot 2", feat(obs, 2, "occupied"), 0.0)

_TARGET_BIT = {
    TargetMode.SINGLE_ENEMY: "targets_enemy",
    TargetMode.ALL_ENEMIES: "targets_all_enemies",
    TargetMode.SELF: "targets_self",
    TargetMode.ALLY: "targets_ally",
    TargetMode.SELF_OR_ALLY: "targets_self_or_ally",
}
_pool = [f() if callable(f) else f for f in C.CARD_POOL_IRONCLAD]
_by_mode = {}
for _c in _pool + make_starter_deck():
    _by_mode.setdefault(_c.target, _c)
_bad = []
for _mode, _card in _by_mode.items():
    p.hand = [_card]
    _o = e._observe()
    _hot = [n for n in ENV.HAND_FEATURE_NAMES
            if n.startswith("targets_") and _o[HAND_OFF + IDX[n]] > 0]
    if _hot != [_TARGET_BIT[_mode]]:
        _bad.append(f"{_card.name} ({_mode.name}): {_hot}")
check("exactly one targeting bit, and the right one, per card",
      _bad, [])
check("...over every targeting mode the pool actually uses",
      sorted(m.name for m in _by_mode),
      ["ALLY", "ALL_ENEMIES", "SELF", "SINGLE_ENEMY"])

check("Strike damage is encoded (6/20)", round(feat(obs, 0, "damage"), 3), 0.3)
check("Defend block is encoded (5/20)", round(feat(obs, 1, "block"), 3), 0.25)
check("Strike cost is encoded (1/6)", round(feat(obs, 0, "cost"), 3), round(1 / 6, 3))

p.hand = [pool("Purity"), pool("Apparition"), pool("Ultimate Strike")]
obs = e._observe()
check("Retain is encoded", feat(obs, 0, "retain"), 1.0)
check("Ethereal is encoded", feat(obs, 1, "ethereal"), 1.0)
check("Exhaust is encoded", feat(obs, 0, "exhausts"), 1.0)
check("a plain card has none of them",
      [feat(obs, 2, k) for k in ("retain", "ethereal", "exhausts")],
      [0.0, 0.0, 0.0])
up = pool("Ultimate Strike")
up.upgrade()
p.hand = [up]
check("upgraded flag is encoded", feat(e._observe(), 0, "upgraded"), 1.0)

p.hand = [C.make_wound(), pool("Injury")]
obs = e._observe()
check("Status type bit", feat(obs, 0, "is_status"), 1.0)
check("Curse type bit", feat(obs, 1, "is_curse"), 1.0)

p.hand = [pool("Volley")]
obs = e._observe()
check("X-cost is flagged", feat(obs, 0, "is_x_cost"), 1.0)
check("...and its cost feature is 0, not a garbage number",
      feat(obs, 0, "cost"), 0.0)

print()
print("The 'playable' feature must match the action mask exactly")
disagree = []
for state_name, apply_state in states:
    for factory in every:
        e2 = make_env()
        p2 = e2._current_player()
        p2.hand = [factory()]
        apply_state(p2)
        obs2 = e2._observe()
        in_obs = feat(obs2, 0, "playable") > 0
        in_mask = 0 in mask_legal_slots(e2)
        if in_obs != in_mask:
            disagree.append(f"{factory().name} [{state_name}]")
check(f"playable feature == mask for {len(every)} cards x {len(states)} states",
      disagree, [])

print()
print("hand_card_ids: the embedding hook")
e = make_env()
p = e._current_player()
p.hand = [make_starter_deck()[0], C.make_wound()]
ids = e.hand_card_ids()
check("length is MAX_HAND", len(ids), ENV.MAX_HAND)
check("slot 0 is Strike's id", int(ids[0]), C.CARD_IDS["Strike"])
check("slot 1 is Wound's id", int(ids[1]), C.CARD_IDS["Wound"])
check("empty slots are -1", int(ids[2]), -1)
check("ids are distinct per card", ids[0] != ids[1], True)

unknown = sorted({f().name for f in every if C.card_id(f()) < 0}
                 | {mk().name for mk in C.STATUS_CARDS if C.card_id(mk()) < 0}
                 | {f().name for f in C.CURSE_POOL if C.card_id(f()) < 0})
check("every pool/status/curse card has an id", unknown, [])
check(f"ids are dense 0..{C.TOTAL_CARD_IDS - 1}",
      sorted(C.CARD_IDS.values()) == list(range(C.TOTAL_CARD_IDS)), True)
check("ids are name-sorted, so they are stable across processes",
      list(C.CARD_IDS) == sorted(C.CARD_IDS), True)

print()
print("pile counts")
e = make_env()
p = e._current_player()
p.hand, p.draw_pile, p.discard_pile, p.exhaust_pile = (
    [make_starter_deck()[0]] * 2, [make_starter_deck()[0]] * 3,
    [make_starter_deck()[0]] * 4, [make_starter_deck()[0]] * 5)
obs = e._observe()
lo, hi = ENV.OBS_OFFSETS["piles"]
PF0 = len(ENV.PILE_FEATURE_NAMES)
counts = [round(float(obs[lo + i * PF0]), 4) for i in range(4)]
check("hand/draw/discard/exhaust totals are still encoded",
      counts, [round(v, 4) for v in (2 / 10.0, 3 / 30.0, 4 / 30.0, 5 / 30.0)])

print()
print("=" * 74)
print("Teammates are capability counts, not raw hands")
print("=" * 74)
from game_engine.observe import (card_capabilities, summarise_hand,
                                 ALLY_FEATURE_NAMES, ALLY_FEATURES,
                                 CAPABILITIES)

_every = ([f() for f in C.CARD_POOL_IRONCLAD]
          + [f() for f in C.COLORLESS_POOL]
          + [f() for f in C.CURSE_POOL]
          + [mk() for mk in C.STATUS_CARDS]
          + make_starter_deck())
_uncovered = sorted({c.name for c in _every if not card_capabilities(c)})
check(f"every one of {len(_every)} pool cards maps to a capability",
      _uncovered, [])
_bad = sorted({cap for c in _every for cap in card_capabilities(c)
               if cap not in CAPABILITIES})
check("...and only to declared capabilities", _bad, [])

e = make_env(players=3)
lo, hi = ENV.OBS_OFFSETS["ally_summary"]
check("the ally block is 3 teammates x 12", hi - lo, 36)
AIDX = {n: i for i, n in enumerate(ALLY_FEATURE_NAMES)}


def mate_feat(obs, slot, name):
    return float(obs[lo + slot * ALLY_FEATURES + AIDX[name]])


mates = e._allies_in_obs_order()
mates[0].hand = [make_starter_deck()[0]] * 3          # 3 Strikes
mates[0].energy = 99
mates[1].hand = [C.make_wound(), C.make_wound()]      # unplayable clutter
obs = e._observe()
check("a teammate's attacks are counted",
      round(mate_feat(obs, 0, "damage") * 10), 3)
check("...with their damage total",
      round(mate_feat(obs, 0, "total_damage") * 100), 18)
check("held clutter shows as `dead`",
      round(mate_feat(obs, 1, "dead") * 10), 2)
check("...and contributes no damage",
      mate_feat(obs, 1, "total_damage"), 0.0)

e1 = make_env(players=1)
o1 = e1._observe()
check("solo leaves the whole ally block at zero",
      float(sum(abs(x) for x in o1[lo:hi])), 0.0)

print()
print("=" * 74)
print("Statuses (#49)")
print("=" * 74)

SIDX = {n: i for i, n in enumerate(ENV.STATUS_CHANNEL_NAMES)}


def status_feats(obs, section, slot):
    off = ENV.OBS_OFFSETS[section][0] + slot * ENV.ENTITY_FEATURES + 3
    return [float(x) for x in obs[off:off + ENV.STATUS_FEATURES]]


def sfeat(obs, section, slot, name):
    return status_feats(obs, section, slot)[SIDX[name]]


e = make_env()
p, en = e._current_player(), e.engine.enemies[0]
o1 = e._observe().copy()
p.add_status(StatusType.STRENGTH, 5)
en.add_status(StatusType.VULNERABLE, 3)
o2 = e._observe().copy()
check("statuses now move the observation", np.array_equal(o1, o2), False)
check("player Strength is encoded (5/10)",
      round(sfeat(o2, "players", 0, "strength"), 3), 0.5)
check("enemy Vulnerable is encoded (3/10)",
      round(sfeat(o2, "enemies", 0, "vulnerable"), 3), 0.3)

e = make_env()
p = e._current_player()
p.add_status(StatusType.STRENGTH, 6)
p.add_status(StatusType.STRENGTH_THIS_TURN, 2)
p.add_status(StatusType.STRENGTH_LOSS, 3)
obs = e._observe()
check("Strength folds THIS_TURN and LOSS (6+2-3 = 5)",
      round(sfeat(obs, "players", 0, "strength"), 3), 0.5)
check("...and matches what deal_attack_damage actually uses",
      p.deal_attack_damage(10) - 10, 5)

e = make_env()
p = e._current_player()
p.add_status(StatusType.SHRINK, 4)
obs = e._observe()
check("an unfolded debuff still shows up in other_debuffs",
      sfeat(obs, "players", 0, "other_debuffs") > 0, True)

e = make_env()
p = e._current_player()
p.add_status(StatusType.STRENGTH_LOSS, 4)
obs = e._observe()
check("negative Strength keeps its sign",
      round(sfeat(obs, "players", 0, "strength"), 3), -0.4)

e = make_env()
p = e._current_player()
p.add_status(StatusType.METALLICIZE, 3)
p.add_status(StatusType.PLATED_ARMOR, 4)
check("Metallicize and Plating fold into one channel",
      round(sfeat(e._observe(), "players", 0, "plating"), 3), 0.7)

e = make_env()
p = e._current_player()
p.add_status(StatusType.RINGING, 1)
check("action-restricting statuses are visible",
      round(sfeat(e._observe(), "players", 0, "restricted"), 3), 0.1)

print()
print("piles by composition")
e = make_env()
p = e._current_player()
lo, hi = ENV.OBS_OFFSETS["piles"]
PF = len(ENV.PILE_FEATURE_NAMES)
PIDX = {n: i for i, n in enumerate(ENV.PILE_FEATURE_NAMES)}
check("the pile block is 4 piles x 8 features", hi - lo, 32)


def pile_feat(obs, pile_name, feat):
    base = lo + ENV.PILE_NAMES.index(pile_name) * PF
    return float(obs[base + PIDX[feat]])


p.hand = [make_starter_deck()[0]] * 3          # 3 Strikes
p.draw_pile = [c for c in make_starter_deck() if c.name == "Defend"][:4]
p.discard_pile = []
p.exhaust_pile = []
obs = e._observe()
check("hand counts 3 attacks", round(pile_feat(obs, "hand", "attacks") * 10), 3)
check("hand counts 0 skills", round(pile_feat(obs, "hand", "skills") * 10), 0)
check("draw counts 4 skills", round(pile_feat(obs, "draw", "skills") * 30), 4)
check("draw counts 0 attacks", round(pile_feat(obs, "draw", "attacks") * 30), 0)
check("hand carries its damage total",
      round(pile_feat(obs, "hand", "damage") * 100), 18)
check("draw carries its block total",
      round(pile_feat(obs, "draw", "block") * 100), 20)
check("an empty pile is all zeros",
      [round(pile_feat(obs, "exhaust", f), 6)
       for f in ENV.PILE_FEATURE_NAMES], [0.0] * PF)


rng2 = np.random.default_rng(7)
penalties = 0
steps2 = 0
for seed in range(20):
    def mk_players():
        pl = Player("P", 80, 3, deck=make_starter_deck())
        return [pl]
    ee = ENV.CombatEnv(mk_players, lambda: [E.make_nibbit()], seed=seed)
    ee.reset()
    pp = ee._current_player()
    done, guard = False, 0
    while not done and guard < 300:
        guard += 1
        mm = ee.legal_action_mask()
        a = int(rng2.choice(np.flatnonzero(mm > 0)))
        _, rew, done, _ = ee.step(a)
        steps2 += 1
        if rew <= -1.0 and not done:
            penalties += 1
check(f"no illegal-action penalty across {steps2} masked steps",
      penalties, 0)

print()
print("=" * 74)
if FAILS:
    print(f"{len(FAILS)} FAILURE(S):")
    for f in FAILS:
        print("   -", f)
    sys.exit(1)
print("ALL ENV CHECKS PASSED")
