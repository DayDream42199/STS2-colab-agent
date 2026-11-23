"""Normalization (step 6): raw combat state -> 15,046 numbers, laid out exactly as the Agent Input spec."""
import math
import numpy as np

from .config import *  # noqa: F401,F403  (constants and offsets)
from .cards import TYPES, TARGETS, KEYWORDS
from .analyzer import profile_vector


def soft(x, ref):
    return x / (x + ref) if x > 0 else 0.0


def clip(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def write_statuses(out, off, statuses):
    for name, v in statuses.items():
        i = STATUS_INDEX.get(name)
        if i is None or v == 0:
            continue
        if name in FLAG_STATUSES:
            out[off + i] = 1.0
        else:
            out[off + i] = v / (abs(v) + STATUS_REF.get(name, STATUS_REF_DEFAULT))


# ---------------------------------------------------------------- cards
_RECIPIENT = {"self": 0, "target": 1, "all_allies": 2, "all_enemies": 3}
_static_cache = {}


def _static_card(defn):
    """The parts of a card vector that never change (type, target, keywords, statuses)."""
    v = _static_cache.get(defn.name)
    if v is not None:
        return v
    v = np.zeros(CARD_SIZE, dtype=np.float32)
    v[TYPES.index(defn.type)] = 1
    v[6 + TARGETS.index(defn.target)] = 1
    for k in defn.keywords:
        v[13 + KEYWORDS.index(k)] = 1
    for recipient, sts in defn.statuses.items():
        base = 19 + _RECIPIENT[recipient] * OUTCOME_SIZE + 3
        tmp = np.zeros(S, dtype=np.float32)
        write_statuses(tmp, 0, sts)
        v[base:base + S] = tmp
    _static_cache[defn.name] = v
    return v


def _damage_recipient(target):
    return {"single_enemy": 1, "random_enemy": 1, "all_enemy": 3}.get(target)


def _block_recipient(defn):
    """Who gets a card's Block: its target, unless the card says otherwise (real engine: Lift, Intercept)."""
    to = getattr(defn, "block_to", None)
    return _RECIPIENT[to] if to is not None else {"single_ally": 1, "all_ally": 2}.get(defn.target, 0)


def write_card(out, off, combat, owner, card):
    d = card.defn
    out[off:off + CARD_SIZE] = _static_card(d)
    out[off + 5] = soft(d.cost, REF_ENERGY)          # no X-cost cards in the mock set
    out[off + 18] = 1.0 if card.upgraded else 0.0
    if d.damage > 0:
        r = _damage_recipient(d.target)
        if r is not None:
            base = off + 19 + r * OUTCOME_SIZE
            out[base] = soft(combat.card_hit(owner, card), REF_DAMAGE)
            out[base + 1] = soft(d.hits, REF_HITS)
    if d.block > 0:
        base = off + 19 + _block_recipient(d) * OUTCOME_SIZE
        out[base + 2] = soft(combat.card_block(owner, card), REF_BLOCK)


_EFFECT_REFS = (REF_HP_COST, REF_HEAL, REF_ENERGY, REF_DRAW, REF_ENERGY, REF_DRAW)


def write_effects(out, off, card):
    """EnvConfig.card_effects: the card's effects (real_engine.card_effects) in its slot of the block after the piles."""
    fx = card.effects
    for i, ref in enumerate(_EFFECT_REFS):
        out[off + i] = soft(fx[i], ref)
    out[off + N_EFFECT_COUNTS:off + EFFECT_SIZE] = fx[N_EFFECT_COUNTS:]


# ---------------------------------------------------------------- piles
def _roles(defn):
    roles = [defn.damage > 0, defn.block > 0, False, False]
    for recipient, sts in defn.statuses.items():
        if recipient in ("target", "all_enemies") and any(s in DEBUFFS for s in sts):
            roles[2] = True
        if recipient in ("self", "all_allies", "target") and any(s in BUFFS for s in sts):
            roles[3] = True
    return roles


def write_pile(out, off, pile):
    n = len(pile)
    if n == 0:
        return
    out[off] = soft(n, REF_PILE_SIZE)
    for c in pile:
        t = c.defn.type
        out[off + 1 + {"attack": 0, "skill": 1, "power": 2}.get(t, 3)] += 1.0 / n
        for i, on in enumerate(_roles(c.defn)):
            if on:
                out[off + 5 + i] += 1.0 / n


# ---------------------------------------------------------------- full encoder
def write_enemy_extra(out, off, statuses):
    """EnvConfig.enemy_statuses: one enemy's ENEMY_EXTRA_STATUSES, in its slot of the block at the end."""
    for i, name in enumerate(ENEMY_EXTRA_STATUSES):
        v = statuses.get(name, 0)
        if v:
            out[off + i] = v / (abs(v) + ENEMY_EXTRA_REF.get(name, STATUS_REF_DEFAULT))


def encode(combat, profiles, choice_cards=(), waited=False, zero_profiles=False, hide_teammates=False, card_effects=False,
           enemy_statuses=False):
    """hide_teammates: the teammates' hand and pile slots stay all zeros.
    card_effects: every card's effects after the piles too (OBS_SIZE_EFFECTS numbers); the rest exactly as without.
    enemy_statuses: then the enemies' ENEMY_EXTRA_STATUSES, ENEMY_EXTRA_SIZE numbers per enemy slot; the rest exactly as without."""
    extra_off = enemy_extra_offset(card_effects)
    out = np.zeros(extra_off + (N_ENEMIES * ENEMY_EXTRA_SIZE if enemy_statuses else 0), dtype=np.float32)
    ally_scale = combat.ally_hp_scale()
    enemy_scale = combat.enemy_hp_scale()

    # Global
    out[0] = math.tanh(math.log2(ally_scale / REF_ALLY_HP) / ALLY_SCALE_RANGE)
    out[1] = math.tanh(math.log2(enemy_scale / REF_ENEMY_HP) / ENEMY_SCALE_RANGE)
    out[2] = soft(combat.turn - 1, REF_TURNS)
    out[3] = 1.0 if choice_cards else 0.0
    out[4] = 1.0 if waited else 0.0

    # Players
    for seat, p in enumerate(combat.players):
        if p is None:
            continue
        off = OFF_PLAYERS + seat * PLAYER_SIZE
        out[off] = 1.0
        out[off + 1] = 1.0 if p.alive else 0.0
        out[off + 2] = 1.0 if (p.ended or not p.alive) else 0.0
        if p.alive:
            inc = combat.incoming(seat)
            out[off + 3] = p.hp / p.max_hp
            out[off + 5] = clip(p.block / ally_scale, 0, 1)
            out[off + 6] = clip((p.hp + p.block - inc) / ally_scale, -1, 1)
            out[off + 7] = clip(p.block / inc, 0, 1) if inc > 0 else 1.0
            out[off + 8] = soft(p.energy, REF_ENERGY)
            write_statuses(out, off + 9, p.statuses)
        out[off + 4] = clip(p.max_hp / ally_scale, 0, 1)
        if seat > 0 and not zero_profiles and seat in profiles:
            out[off + 9 + S: off + 9 + S + 6] = profile_vector(profiles[seat])

    # Enemies (dead and empty slots stay all zeros)
    for slot, e in enumerate(combat.enemies):
        if e is None or not e.alive:
            continue
        off = OFF_ENEMIES + slot * ENEMY_SIZE
        out[off] = 1.0
        out[off + 1] = e.hp / e.max_hp
        out[off + 2] = clip(e.max_hp / enemy_scale, 0, 1)
        out[off + 3] = soft(e.hp, REF_DAMAGE)
        out[off + 4] = soft(e.block, REF_DAMAGE)
        write_statuses(out, off + 5, e.statuses)
        if enemy_statuses:
            write_enemy_extra(out, extra_off + slot * ENEMY_EXTRA_SIZE, e.statuses)
        it = e.intent
        ioff = off + 5 + S
        for i, kind in enumerate(("attack", "block", "buff", "debuff", "other")):
            if kind in it.kinds:
                out[ioff + i] = 1.0
        agent = combat.players[0]
        if "attack" in it.kinds and it.target == 0 and agent.alive:
            out[ioff + 5] = clip(combat.enemy_hit(e, agent) * it.hits / ally_scale, 0, 1)
        if "attack" in it.kinds:
            out[ioff + 6] = soft(it.hits, REF_HITS)

    # Cards: my hand, teammates' hands, choice slots
    for seat, p in enumerate(combat.players):
        if p is None or (hide_teammates and seat > 0):
            continue
        for h, card in enumerate(p.hand[:HAND_SIZE]):
            write_card(out, OFF_CARDS + (seat * HAND_SIZE + h) * CARD_SIZE, combat, p, card)
            if card_effects:
                write_effects(out, OFF_EFFECTS + (seat * HAND_SIZE + h) * EFFECT_SIZE, card)
    for k, card in enumerate(choice_cards[:N_CHOICE]):
        write_card(out, OFF_CARDS + (N_PLAYERS * HAND_SIZE + k) * CARD_SIZE, combat, combat.players[0], card)
        if card_effects:
            write_effects(out, OFF_EFFECTS + (N_PLAYERS * HAND_SIZE + k) * EFFECT_SIZE, card)

    # Piles: draw, discard, exhaust per player
    for seat, p in enumerate(combat.players):
        if p is None or (hide_teammates and seat > 0):
            continue
        for i, pile in enumerate((p.draw, p.discard, p.exhaust)):
            write_pile(out, OFF_PILES + (seat * N_PILES + i) * PILE_SIZE, pile)

    return out
