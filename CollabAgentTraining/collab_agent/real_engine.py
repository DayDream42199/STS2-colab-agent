"""The env's engine interface on top of the real 2nd_model engine (Server/GameEngine).

    EnvConfig(engine="real")            # python train.py --engine real

CollabEnv, observation.py and bots.py talk to an engine through a small set of
names (README, "Plugging in the real engine"); this module gives them those
names over the real Combat, so they run unchanged. A fight here is the real
thing: Ironclads with the real cards (any of them, with their questions), the
Act 1 enemies and their intents, co-op enemy scaling. Turns are simultaneous
as in the game - anyone acts whenever, the round ends once every player still
standing has ended - and every enemy attack lands on every player.

Two things the real engine does not keep, added here from each action's results:
  - each turn's analyzer input, gathered by the aura plugin's own hooks
    (Server/Plugins/aura.py), so the profiles get exactly what a real game logs;
  - the numbers the rewards read (engine.new_stats): who put the Vulnerable and
    Weak on each enemy (stacks per player), the agent's debuffs and the Block it
    gave, teammates' hits on its Vulnerable and the HP they took off because of
    it (the hit with the Vulnerable multiplier undone), and - worked out from the
    intents just before each enemy turn - the HP its Weak and its Block will save
    each teammate.

The 2nd_model Server folder is found next to this repo folder
(../2nd_model/Server), or wherever STS2_SERVER points.
"""
import itertools
import math
import os
import random
import sys
from types import SimpleNamespace

SERVER = os.environ.get("STS2_SERVER") or os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "2nd_model", "Server"))
if not os.path.isdir(os.path.join(SERVER, "GameEngine")):
    raise ImportError(f"the real engine is not at {SERVER}: set STS2_SERVER to 2nd_model/Server")
if SERVER not in sys.path:
    sys.path.append(SERVER)          # at the end: nothing there may hide a module of this repo

from GameEngine.Cards._card import Card as _Card                                   # noqa: E402
from GameEngine.Cards._card_enums import CardClass                                 # noqa: E402
from GameEngine.Cards._card_ref import is_upgraded                                 # noqa: E402
from GameEngine.Combat.combat import Combat as _Combat, CombatPhase, CombatResult  # noqa: E402
from GameEngine.Context.context import PendingChoice                               # noqa: E402
from GameEngine.Effects.StatusEffects.vulnerable import Vulnerable                 # noqa: E402
from GameEngine.Registry.card_registry import create_card, generatable_card_ids    # noqa: E402
from GameEngine.Registry.unit_registry import create_ally, create_enemy            # noqa: E402
from GameEngine.Resolution.resolver import Resolver                                # noqa: E402
from Plugins.aura import create_plugin as _create_aura, _incoming                  # noqa: E402
from Plugins.card_groups import card_info, describe_card, _flat, _play_in_sandbox  # noqa: E402

from .cards import KEYWORDS                                                        # noqa: E402
from .config import N_PLAYERS, N_ENEMIES, EFFECT_NAMES, N_EFFECT_COUNTS            # noqa: E402
from .engine import Question, new_stats                                            # noqa: E402

# ---------------------------------------------------------------- fights
# Act 1 lineups, from 2nd_model's ported Overgrowth and Underdocks (COMBAT_INTERFACE.md's
# enemy table). Edit freely: any registered enemy ids work.
HALLWAY = (
    ("nibbit",), ("nibbit", "nibbit"), ("leafslimemedium", "twigslimesmall"),
    ("twigslimemedium", "leafslimesmall"), ("fuzzywurmcrawler",), ("shrinkerbeetle",),
    ("slitheringstrangler",), ("vineshambler",), ("mawler",), ("cubexconstruct",), ("flyconid",),
    ("inklet", "inklet", "inklet"), ("fogmog",),
    ("seapunk",), ("sewerclam",), ("hauntedship",), ("sludgespinner",), ("punchconstruct",),
    ("calcifiedcultist", "dampcultist"), ("toadpole", "toadpole"), ("corpseslug", "corpseslug"),
    ("fossilstalker",), ("gremlinmerc",), ("livingfog",), ("twotailedrat", "twotailedrat", "twotailedrat"),
)
ELITES = (("phrogparasite",), ("bygoneeffigy",), ("byrdonis",), ("terroreel",), ("skulkingcolony",),
          ("phantasmalgardener",) * 4)
BOSSES = (("kinfollower", "kinfollower", "kinpriest"), ("vantom",), ("ceremonialbeast",),
          ("lagavulinmatriarch",), ("soulfysh",), ("waterfallgiant",))
POOLS = {"hallway": HALLWAY, "elite": ELITES, "boss": BOSSES}

STARTER = ["strike"] * 5 + ["defend"] * 4 + ["bash"]
# Cards for the team (the game's co-op cards), on top of the Ironclad's own pool
TEAM_CARDS = ("rally", "coordinate", "lift", "beacon_of_hope", "huddle_up", "believe_in_you",
              "intercept", "tag_team", "gang_up", "knockdown", "mimic", "shockwave")
# Whole decks for tests, every seat the same (--deck). "teamwork": the starter, 10 cards whose worth
# depends on the teammate (Block for them, Strength and energy for them, debuffs, team payoffs) and
# 4 Powers, so there is something to build up with (the scale bot, the S trait).
FIXED_DECKS = {"teamwork": tuple(STARTER) + ("lift", "intercept", "rally", "coordinate", "believe_in_you",
                                             "tremble", "shockwave", "uppercut", "gang_up", "tag_team",
                                             "inflame", "stone_armor", "demon_form", "beacon_of_hope")}
# Varied decks from one whole deck (--deck-presets): how many cards of each kind (card_kinds) a player is dealt. These are
# the playtest's presets (playtest.DECK_PRESETS): keep the two the same. WHOLE_DECK names the whole deck for every seat.
WHOLE_DECK = "Whole"
# POOL_DECK: each seat the Ironclad's starter and cfg.real_pool_cards cards from card_pool(), so a run naming it in
# --deck-presets mixes the whole deck and its presets with cards from the whole pool. Not a preset: the playtest has none.
POOL_DECK = "Pool"
DECK_PRESETS = {"Default": dict(block=4, attack=5, skill=3, power=2),
                "Small": dict(block=2, attack=3, skill=1, power=1),
                "Bloated": dict(block=7, attack=10, skill=5, power=4),
                "Helper": dict(block=4, attack=5, skill=3, power=2, helper=3)}


def card_pool():
    """What a deck's extra cards are drawn from: every Ironclad card a fight can generate
    (Common, Uncommon, Rare) and the co-op cards."""
    return tuple(sorted(set(generatable_card_ids(CardClass.IRONCLAD)) | set(TEAM_CARDS)))


class Seat:
    """A player kept for a team's fights: its deck and, for a teammate, its bot."""

    def __init__(self, seat, deck, bot=None):
        self.seat, self.deck, self.bot = seat, deck, bot


def card_kinds(cards):
    """A deck's cards by kind, every copy kept: block (a skill that gives Block), skill (one that does not), attack,
    power, and helper (aimed at a teammate or every player; a helper card is also a block or skill card)."""
    kinds = {}
    for card in cards:
        s = _static(card)
        if s.type in ("attack", "power"):
            kinds.setdefault(s.type, []).append(card)
        elif s.type == "skill":
            kinds.setdefault("block" if s.blocks else "skill", []).append(card)
        if s.target in ("single_ally", "all_ally"):
            kinds.setdefault("helper", []).append(card)
    return kinds


def deal_deck(rng, kinds, preset):
    """One player's deck from a preset: each card drawn at random from the cards of its kind, so a card the whole
    deck holds five of comes up five times as often as one it holds once, and nobody gets a card it lacks."""
    return [str(c) for kind, n in DECK_PRESETS[preset].items() for c in rng.choice(kinds[kind], size=n)]


def make_team(rng, bots, cfg):
    """Seat 0 = the agent, then one seat per teammate bot; each deck cfg.real_deck if set, else
    the Ironclad's starter and cfg.real_extra_cards cards from card_pool(). With cfg.real_deck_presets
    the team is dealt one of those kinds, drawn at random: the whole deck for every seat (WHOLE_DECK),
    a preset, each seat its own deck from the whole deck's cards (deal_deck), or POOL_DECK, each seat the
    starter and cfg.real_pool_cards cards from card_pool()."""
    pool = card_pool()
    preset = str(rng.choice(cfg.real_deck_presets)) if cfg.real_deck and cfg.real_deck_presets else WHOLE_DECK
    kinds = card_kinds(cfg.real_deck) if preset not in (WHOLE_DECK, POOL_DECK) else None
    starter = lambda n: STARTER + [str(c) for c in rng.choice(pool, size=n, replace=False)]
    deck = lambda: (deal_deck(rng, kinds, preset) if kinds else starter(cfg.real_pool_cards) if preset == POOL_DECK else
                    list(cfg.real_deck) if cfg.real_deck else starter(cfg.real_extra_cards))
    team = [Seat(0, deck())] + [Seat(i, deck(), bot) for i, bot in enumerate(bots, start=1)]
    for seat in team:
        seat.preset = preset if cfg.real_deck and cfg.real_deck_presets else None     # for tests and reports
    return team


def new_fight(rng, seats, cfg):
    """A fight for the team: a lineup from the pools (cfg.real_pool_weights over hallway,
    elite, boss), each player a fresh character holding its seat's deck, at full HP or, with
    cfg.start_hp, at a share of max HP drawn separately for each player."""
    names = list(POOLS)
    weights = [cfg.real_pool_weights[i] for i in range(len(names))]
    pool = POOLS[names[int(rng.choice(len(names), p=[w / sum(weights) for w in weights]))]]
    lineup = pool[int(rng.integers(len(pool)))]
    combat = start_fight(lineup, seats, cfg.real_ally, int(rng.integers(2 ** 31)))
    if cfg.start_hp:
        combat.set_start_hp([float(rng.choice(cfg.start_hp)) for _ in combat.allies])
    return combat


def start_fight(lineup, seats, ally="ironclad", seed=0):
    """One fight against `lineup` (enemy type ids, in order), as new_fight sets it up."""
    allies = []
    for seat in seats:
        unit = create_ally(ally, f"p{seat.seat + 1}", rng=random.Random(seed + seat.seat))
        unit.deck = list(seat.deck)
        allies.append(unit)
    enemies = [create_enemy(kind, f"e{i + 1}") for i, kind in enumerate(lineup)]
    combat = _Combat(allies, enemies, rng=random.Random(seed), act="act1", scale_enemies=True)
    combat.ask_players = True            # the agent's and the bots' questions wait for an answer
    combat.start()
    return RealCombat(combat, seats, lineup)


# ---------------------------------------------------------------- what observation.py and bots.py read
_TYPES = {"ATTACK": "attack", "SKILL": "skill", "POWER": "power", "STATUS": "status", "CURSE": "curse",
          "QUEST": "skill"}
_TARGETS = {"ENEMY": "single_enemy", "ALL_ENEMIES": "all_enemy", "RANDOM_ENEMY": "random_enemy",
            "SELF": "self", "ALLY": "single_ally", "ALL_ALLIES": "all_ally", "RANDOM_ALLY": "single_ally"}
_STATIC = {}
_uid = itertools.count()
# Where a card's Block goes when its target does not say. Lift's is all the teammate's, so Combat.hand_blocks
# (what the holder gains) has no number for it. Intercept's is the holder's; the teammate it targets is only covered.
BLOCK_TO = {"lift": "target", "intercept": "self"}


def _static(ref):
    """What never changes about a card (id + upgraded): cached."""
    key = (str(ref), is_upgraded(ref))
    s = _STATIC.get(key)
    if s is None:
        info = card_info(*key)
        card = create_card(ref)
        block_to = BLOCK_TO.get(card.card_id)
        s = SimpleNamespace(
            name=card.name + ("+" if key[1] else ""),     # observation.py caches a card's fixed part by name
            type=_TYPES[info["type"]], target=_TARGETS.get(info["target"], "none"),
            keywords=frozenset(k for k in info["keywords"] if k in KEYWORDS),
            statuses={scope: dict(v) for scope, v in info["statuses"].items() if v},
            groups=frozenset(info["groups"]), hits=info["hits"], x_cost=info["x_cost"],
            printed_cost=0 if not card.properties.playable or card.cost == _Card.X_COST else card.cost,
            damages="damage" in info["signals"], blocks="block" in info["signals"] or block_to == "target",
            block_to=block_to, teammate_block=getattr(card, "BLOCK", 0) if block_to == "target" else 0)
        _STATIC[key] = s
    return s


# What a card does beyond its damage, Block and statuses (EnvConfig.card_effects), from the same sandbox plays
# card_groups.card_info reads a card from: one per hand (mixed, all Attacks, no Attacks, empty), the counts from the first.
_EFFECT_OF = {"instant_exhaust": "exhausts", "instant_add_card": "adds", "instant_move_card": "moves",
              "instant_upgrade_card": "improves", "instant_boost_card": "improves", "instant_raise_cost": "improves",
              "instant_cap_cost": "improves", "instant_grant_replay": "improves", "instant_play_card": "plays"}
_EFFECTS = {}


def card_effects(ref):
    """config.EFFECT_NAMES for one card (id + upgraded): HP its holder loses and heals, energy and cards it gains, energy
    and cards a teammate gains, then 1 or 0 for exhausting, adding, moving, improving and playing cards. Cached. Read only
    when the input asks for it, and the global random state is put back, so a real fight never sees the sandbox."""
    key = (str(ref), is_upgraded(ref))
    fx = _EFFECTS.get(key)
    if fx is None:
        state = random.getstate()
        try:
            fx = _measure_effects(*key)
        finally:
            random.setstate(state)
        _EFFECTS[key] = fx
    return fx


def _measure_effects(card_id, upgraded):
    info = card_info(card_id, upgraded)
    counts, flags = None, set()
    if "unplayable" not in info["keywords"]:
        for filler in (["strike", "defend", "wound"], ["strike", "strike"], ["defend", "defend"], []):
            play = _play_in_sandbox(card_id, upgraded, filler, 1 if info["x_cost"] else 10)
            if play is None:
                continue
            results, allies = play[2], play[5]
            me, mate = allies[0].unit_id, allies[1].unit_id
            got = dict.fromkeys(EFFECT_NAMES[:N_EFFECT_COUNTS], 0)
            for result in _flat(results):
                effect, target, amount = result.get("effect_id"), result.get("target_id"), result.get("amount") or 0
                if target not in (me, mate):
                    continue
                mine = target == me
                if effect == "instant_energy":
                    got["energy" if mine else "mate_energy"] += amount
                elif effect in ("instant_draw", "instant_draw_until"):
                    got["draws" if mine else "mate_draws"] += amount
                elif mine and effect == "instant_hp_loss":
                    got["hp_lost"] += amount
                elif mine and effect == "instant_heal":
                    got["healed"] += amount
                elif mine and effect in _EFFECT_OF:
                    flags.add(_EFFECT_OF[effect])
            if counts is None:
                counts = got
    counts = counts or {}
    return (tuple(max(0, counts.get(name, 0)) for name in EFFECT_NAMES[:N_EFFECT_COUNTS]) +
            tuple(int(name in flags) for name in EFFECT_NAMES[N_EFFECT_COUNTS:]))


class Defn:
    """A card as the mock's CardDef shows it: fixed parts plus this copy's numbers now."""
    __slots__ = ("name", "type", "cost", "target", "damage", "hits", "block", "block_to", "statuses", "keywords",
                 "groups", "choice")

    def __init__(self, s, cost, damage, hits, block):
        self.name, self.type, self.target = s.name, s.type, s.target
        self.statuses, self.keywords, self.groups = s.statuses, s.keywords, s.groups
        self.cost, self.damage, self.hits, self.block = cost, damage, hits, block
        self.block_to = s.block_to
        self.choice = None


class CardView:
    """One card: `defn` for the reader and the bots, `hit` / `blk` its damage per hit and
    Block now, `index` its option number when it is a question's option."""
    __slots__ = ("ref", "defn", "uid", "upgraded", "hit", "blk", "index")

    def __init__(self, ref, defn, hit, blk, index=None):
        self.ref, self.defn, self.hit, self.blk, self.index = ref, defn, hit, blk, index
        self.uid = next(_uid)
        self.upgraded = is_upgraded(ref)

    @property
    def name(self):
        return self.defn.name

    @property
    def effects(self):
        """card_effects of this card: only the input reads it, and only with EnvConfig.card_effects."""
        return card_effects(self.ref)

    def __repr__(self):
        return f"<{self.defn.name}>"


def _hand_view(combat, ally):
    """The hand with the numbers it shows now (as Combat.hand_costs / hand_damages / hand_blocks)."""
    costs, damages, blocks = combat.hand_costs(ally), combat.hand_damages(ally), combat.hand_blocks(ally)
    out = []
    for i, ref in enumerate(ally.hand):
        s = _static(ref)
        cost = costs[i]
        cost = ally.energy if cost == _Card.X_COST else (cost or 0)
        hits = s.hits * (ally.energy if s.x_cost else 1)
        hit, blk = damages[i] or 0, blocks[i] or s.teammate_block
        out.append(CardView(ref, Defn(s, cost, hit, hits, blk), hit, blk))
    return out


def _pile_view(pile):
    """Cards out of hand: only what the pile summary reads (type, does it deal damage /
    give Block, which statuses)."""
    out = []
    for ref in pile:
        s = _static(ref)
        out.append(CardView(ref, Defn(s, s.printed_cost, int(s.damages), s.hits, int(s.blocks)),
                            int(s.damages), int(s.blocks)))
    return out


def _option_view(ref, holder, index):
    """A question's option, with its own numbers before any status (describe_card)."""
    s, d = _static(ref), describe_card(ref, holder)
    cost = d["cost"]
    cost = holder.energy if cost == _Card.X_COST else (cost or 0)
    hit, blk = d["damage"] or 0, d["block"] or s.teammate_block
    return CardView(ref, Defn(s, cost, hit, d["hits"], blk), hit, blk, index)


class PlayerView:
    def __init__(self, seat, ally, bot, combat):
        self.seat, self.bot, self.unit = seat, bot, ally
        self.hp, self.max_hp, self.block = ally.current_hp, ally.max_hp, ally.block
        self.energy, self.max_energy = ally.energy, ally.max_energy
        self.alive = ally.is_alive()
        self.statuses = _statuses(ally)
        self.ended = ally.unit_id in combat.ended_turn or not self.alive
        self.hand = _hand_view(combat, ally) if self.alive else []
        self.draw, self.discard, self.exhaust = (_pile_view(ally.draw_pile), _pile_view(ally.discard_pile),
                                                 _pile_view(ally.exhaust_pile))
        self.history = None      # the turn records go out through RealCombat.finished_histories


class IntentView:
    """An enemy's intent as the mock's Intent: kinds, damage per hit as printed, hits, and
    `target` 0 when the agent is hit (every attack lands on every player); damage_to holds
    what one hit does to each player, after Strength, Weak and their Vulnerable."""

    def __init__(self, intent, agent_id):
        intent = intent or {}
        kind = intent.get("type") or "other"
        kinds = set()
        if kind == "attack":
            kinds.add("attack")
            if intent.get("block"):
                kinds.add("block")
        elif kind == "block":
            kinds.add("block")
        elif kind == "buff":
            kinds.add("buff")
        elif kind.startswith("debuff"):
            kinds.add("debuff")
        else:
            kinds.add("other")              # summon, sleep, stun, heal, escape
        self.kinds = kinds
        self.damage, self.hits = intent.get("amount", 0) or 0, intent.get("hits", 1) or 1
        self.damage_to = intent.get("damage", {}) if kind == "attack" else {}
        self.target = 0 if agent_id in self.damage_to else None
        self.block = intent.get("block", 0) or 0


class EnemyView:
    def __init__(self, slot, enemy, combat, agent_id, entered_max_hp):
        self.slot, self.unit = slot, enemy
        self.hp, self.max_hp, self.block = enemy.current_hp, enemy.max_hp, enemy.block
        if getattr(enemy, "blowing", None) is not None:
            # A Waterfall Giant brought down holding Steam is not dead: 999,999,999 HP, out of
            # reach, until it explodes two moves on. Beaten, as far as anyone can hurt it.
            self.hp, self.max_hp = 0, entered_max_hp
        self.alive = enemy.is_alive()
        self.statuses = _statuses(enemy)
        self.intent = IntentView(combat._enemy_dict(enemy).get("intent"), agent_id)


def _statuses(unit):
    out = {}
    for sid, status in unit.statuses.items():
        amount = getattr(status, "amount", None)
        out[sid] = 1 if amount is None else amount
    return out


def _history(ended):
    """aura's turn as it ended -> the record analyzer.to_history reads."""
    card = lambda v: [v["cost"], v["dmg"], v["block"], set(v["groups"])]
    return {"E_total": ended["energy"], "used": [card(v) for v in ended["used"]],
            "leftover": [card(v) for v in ended["hand"]], "opp": [card(v) for v in ended["opp"]],
            "intent": ended["incoming"], "end_block": ended["block"], "turn": ended["turn"]}


# ---------------------------------------------------------------- the adapter
class RealCombat:
    """One real fight, seen through the mock Combat's names."""

    BOT_ACTIONS_PER_TURN = 60            # a bot still going after this many is made to end its turn

    def __init__(self, combat, seats, lineup=()):
        self.combat = combat
        self.lineup = tuple(lineup)
        self.seats = seats
        self.allies = list(combat.allies)                     # seat i = allies[i] = p{i+1}
        self.seat_of = {ally.unit_id: i for i, ally in enumerate(self.allies)}
        self.agent_id = self.allies[0].unit_id
        self.stats = new_stats()
        self.finished_histories = {}
        self.question = None
        self.version = 0
        self.result = None
        self.turn = combat.turn_number
        self.owners = {}                     # enemy id -> {"vulnerable"/"weak": {seat: stacks}}
        self.agent_block = [0] * N_PLAYERS   # Block the agent gave each seat this turn
        self.entered = {}                    # enemy id -> max HP, every enemy that has been in the fight
        self.total_enemy_max_hp = 0
        self._hp = [a.current_hp for a in self.allies]
        self._alive = [a.is_alive() for a in self.allies]
        self._aura = _create_aura()
        self._shim = SimpleNamespace(combat=combat)           # all aura's gathering hooks read
        self._aura.on_turn_start(self._shim)
        self._view_version = None
        self._ending = False
        self._sync()

    def set_start_hp(self, shares):
        """Each player's HP before the fight's first move, as a share of max HP (at least 1 HP)."""
        for i, (ally, share) in enumerate(zip(self.allies, shares)):
            ally.current_hp = max(1, int(round(ally.max_hp * share)))
            self._hp[i] = ally.current_hp
        self.version += 1

    # ------------------------------------------------------------ views
    def _refresh(self):
        if self._view_version == self.version:
            return
        c = self.combat
        players = [PlayerView(i, a, self.seats[i].bot, c) for i, a in enumerate(self.allies)]
        self._players = players + [None] * (N_PLAYERS - len(players))
        living = [e for e in c.enemies if e.is_alive()][:N_ENEMIES]
        enemies = [EnemyView(slot, e, c, self.agent_id, self.entered.get(e.unit_id, e.max_hp))
                   for slot, e in enumerate(living)]
        self._enemies = enemies + [None] * (N_ENEMIES - len(enemies))
        self._view_version = self.version

    @property
    def players(self):
        self._refresh()
        return self._players

    @property
    def enemies(self):
        self._refresh()
        return self._enemies

    def living_players(self):
        return [p for p in self.players if p is not None and p.alive]

    def living_enemies(self):
        return [e for e in self.enemies if e is not None and e.alive]

    def ally_hp_scale(self):
        return max(a.max_hp for a in self.allies)

    def enemy_hp_scale(self):
        return max([e.max_hp for e in self.living_enemies()] or [1])

    def incoming(self, seat):
        ally = self.allies[seat]
        return _incoming(self.combat, ally) if ally.is_alive() else 0

    def enemy_hit(self, enemy, player, ignore_weak=False):
        return enemy.intent.damage_to.get(player.unit.unit_id, 0)

    def card_hit(self, player, card, enemy=None):
        return card.hit

    def card_block(self, player, card):
        return card.blk

    def shown_damage(self, player, card):
        n = len(self.living_enemies()) if card.defn.target == "all_enemy" else 1
        return card.hit * card.defn.hits * n

    # ------------------------------------------------------------ actions
    def legal_plays(self, seat):
        """(hand slot, target) for every play the engine would accept now. Targets: 0 none (or
        the agent), 1-3 teammates, 4-9 the living enemies in fight order."""
        ally = self.allies[seat]
        slots = {e.unit.unit_id: 4 + e.slot for e in self.living_enemies()}
        out = []
        for a in self.combat.legal_actions(ally):
            if a["type"] != "play_card":
                continue
            target = a["target_id"]
            if target is None:
                out.append((a["hand_index"], 0))
            elif target in self.seat_of:
                out.append((a["hand_index"], self.seat_of[target]))
            elif target in slots:
                out.append((a["hand_index"], slots[target]))
        return out

    def _target_unit(self, ally, card_ref, t):
        target = create_card(card_ref).target_type.name
        if target == "ENEMY":
            enemy = self.enemies[t - 4] if 4 <= t < 4 + N_ENEMIES else None
            if enemy is None:
                raise ValueError(f"no enemy in target slot {t}")
            return enemy.unit
        if target == "ALLY":
            return self.allies[t]
        return None

    def play(self, seat, h, t):
        """Play hand slot h on target t. Returns the agent's next question, if it has one."""
        c, ally = self.combat, self.allies[seat]
        ref = ally.hand[h]
        target = self._target_unit(ally, ref, t)
        played = {"action": "play", "unit_id": ally.unit_id, "hand_index": h,
                  "target_id": target.unit_id if target is not None else None,
                  "card_id": str(ref), "upgraded": is_upgraded(ref),
                  "cost": c.hand_costs(ally)[h], "damage": c.hand_damages(ally)[h],
                  "block": c.hand_blocks(ally)[h], "energy": ally.energy}
        before, standing = self._before_action(), [a.is_alive() for a in self.allies]
        results = c.play_card(ally, h, target=target)
        self._aura.on_action(self._shim, dict(played, results=results))
        self._note(results, before)
        self._sync()
        if [a.is_alive() for a in self.allies] != standing:   # a knockout (Bloodletting at low HP) can
            self._maybe_end_round()                           # leave only players who have ended
        return self.pending_question(0) if seat == 0 else None

    def pending_question(self, seat):
        """The question this seat has to answer now (one pick; "up to" ones may stop), or None."""
        ally = self.allies[seat]
        ask = self.combat.choice_for(ally)
        if ask is None:
            return None
        options = [_option_view(ref, ally, i) for i, ref in enumerate(ask.options)]
        q = Question(seat, None, options, 0 if ask.can_stop else 1, 1, 0)
        if seat == 0:
            self.question = q
        return q

    def answer_question(self, picks, seat=0):
        """Answer the open question with the picked option (none: stop). Returns the agent's
        next question, if it has one."""
        ally = self.allies[seat]
        ask = self.combat.choice_for(ally)
        if ask is None:
            return None
        if picks:
            index = picks[0].index
        else:
            index = PendingChoice.STOP if ask.can_stop else 0
        before = self._before_action()
        results = self.combat.answer_choice(ally, index)
        self._aura.on_action(self._shim, {"action": "choose", "unit_id": ally.unit_id, "option_index": index})
        self._note(results, before)
        self._sync()
        if seat == 0:
            self.question = None
        self._maybe_end_round()               # an answer can be the last thing a round waited on
        return self.pending_question(0) if seat == 0 else None

    def end_turn(self, seat):
        ally = self.allies[seat]
        self.combat.end_turn(ally)
        self._aura.on_turn_ended(self._shim, ally.unit_id)
        self._sync()
        self._maybe_end_round()

    # ------------------------------------------------------------ scripted teammates
    def bot_step(self, seat):
        """The bot at `seat` takes one action: an answer it owes, a play (with its answers),
        or ending its turn. False if it has nothing to do."""
        if seat >= len(self.allies) or self.result is not None or self.combat.phase != CombatPhase.PLAYER_TURN:
            return False
        ally = self.allies[seat]
        if not ally.is_alive():
            return False
        if self.combat.choice_for(ally) is not None:
            self._bot_answer(seat)
            return True
        if ally.unit_id in self.combat.ended_turn:
            return False
        action = self.seats[seat].bot.act(self, seat)
        if action[0] == "end":
            self.end_turn(seat)
        else:
            self.play(seat, action[1], action[2])
            while self.result is None and self.combat.choice_for(ally) is not None:
                self._bot_answer(seat)
        return True

    def bot_finish_turn(self, seat):
        turn, steps = self.turn, 0
        while self.turn == turn and self.bot_step(seat):
            steps += 1
            ally = self.allies[seat]
            if (steps >= self.BOT_ACTIONS_PER_TURN and self.result is None and ally.is_alive()
                    and ally.unit_id not in self.combat.ended_turn and self.combat.choice_for(ally) is None):
                self.end_turn(seat)

    def _bot_answer(self, seat):
        """A bot's answer: the random bot picks at random (or stops, when it may), the
        others take the first option - as 2nd_model's scripted teammates do. The mock's
        Bot.answer ranks cards for exhausting, which is not what most real questions ask."""
        q = self.pending_question(seat)
        bot = self.seats[seat].bot
        rng = getattr(bot, "rng", None)
        if rng is not None:
            k = int(rng.integers(len(q.options) + (1 if q.min_picks == 0 else 0)))
            picks = [q.options[k]] if k < len(q.options) else []
        else:
            picks = q.options[:1]
        self.answer_question(picks, seat)

    # ------------------------------------------------------------ the round
    def _maybe_end_round(self):
        """Once every player still standing has ended and nobody is answering anything,
        the enemies take their turn and the next round begins."""
        c = self.combat
        if self._ending or self.result is not None or c.phase != CombatPhase.PLAYER_TURN:
            return
        self._ending = True                    # the bots' answers below come back here: once is enough
        try:
            # A player knocked out mid-play can still hold that card's question (an Exhaust after
            # the HP it cost): nobody will answer it, and the round waits on every question. It
            # goes as the engine's rule for a player who has left: answered at random.
            for seat, ally in enumerate(self.allies):
                if self.result is None and not ally.is_alive() and c.choice_for(ally) is not None:
                    before = self._before_action()
                    self._note(c.forfeit_choices(ally), before)
                    self._sync()
                    if seat == 0:
                        self.question = None
            for seat in range(1, len(self.allies)):            # a teammate's question, asked by
                ally = self.allies[seat]                       # someone else's card: its bot answers
                while self.result is None and ally.is_alive() and c.choice_for(ally) is not None:
                    self._bot_answer(seat)
            if self.result is None and not c.pending_choices and not any(
                    a.is_alive() and a.unit_id not in c.ended_turn for a in self.allies):
                self._end_round()
        finally:
            self._ending = False

    def _end_round(self):
        c = self.combat
        self._before_enemy_turn()
        self.finished_histories = {}
        for seat, ally in enumerate(self.allies):
            turn = self._aura.turns.get(ally.unit_id)
            if turn is not None and turn.ended is not None and turn.alive_at_start:
                self.finished_histories[seat] = _history(turn.ended)
        c.end_player_turn()
        self.stats["rounds"] += 1
        self.agent_block = [0] * N_PLAYERS
        if not c.is_over():
            self._aura.on_turn_start(self._shim)
        self._sync()

    def _before_enemy_turn(self):
        """The HP the agent's Weak and its Block will save each teammate in the enemy turn
        about to come, from the intents: each attacker's damage with and without the Weak
        (Resolver.damage_amount, the same arithmetic the hit uses), and the teammate's Block
        with and without the agent's share of it (taken last)."""
        c, st = self.combat, self.stats
        for seat in range(1, len(self.allies)):
            ally = self.allies[seat]
            if not ally.is_alive():
                continue
            attacks = []
            for enemy in c.enemies:
                if not enemy.is_alive():
                    continue
                intent = c._enemy_dict(enemy).get("intent") or {}
                if intent.get("type") == "attack":
                    attacks.append((enemy, intent))
            hits = {id(e): i.get("damage", {}).get(ally.unit_id, 0) * (i.get("hits", 1) or 1) for e, i in attacks}
            total, block, hp = sum(hits.values()), ally.block, ally.current_hp
            lost = lambda t, b: min(hp, max(0, t - b))
            now = lost(total, block)
            for enemy, intent in attacks:
                share = self._share(enemy.unit_id, "weak")
                if share <= 0:
                    continue
                saved_statuses = enemy.statuses
                enemy.statuses = {k: v for k, v in saved_statuses.items() if k != "weak"}
                try:
                    without = Resolver.damage_amount(enemy, ally, intent.get("amount", 0)) * (intent.get("hits", 1) or 1)
                finally:
                    enemy.statuses = saved_statuses
                saved = lost(total - hits[id(enemy)] + without, block) - now
                if saved > 0:
                    st["hp_saved"] += saved * share
                    st["weak_cashed"] += share
            given = min(self.agent_block[seat], block)
            saved = lost(total, block - given) - now
            if saved > 0:
                st["hp_saved"] += saved
                st["block_cashed"] += 1

    def stall_report(self):
        """What a round that will not end is waiting on, for an error message."""
        c = self.combat
        asks = {uid: (ask.prompt, [str(o) for o in ask.options]) for uid, ask in c.pending_choices.items()}
        waiting = [a.unit_id for a in self.allies if a.is_alive() and a.unit_id not in c.ended_turn]
        dead = [a.unit_id for a in self.allies if not a.is_alive()]
        return (f"lineup {self.lineup}, phase {c.phase.name}, questions open {asks}, not ended {waiting}, "
                f"knocked out {dead}")

    # ------------------------------------------------------------ bookkeeping
    def _share(self, enemy_id, status):
        owners = self.owners.get(enemy_id, {}).get(status, {})
        total = sum(owners.values())
        return owners.get(0, 0) / total if total > 0 else 0.0

    def _before_action(self):
        """Before an action: each living enemy's Vulnerable and Weak stacks, and the agent's
        share of its Vulnerable."""
        amounts, shares = {}, {}
        for e in self.combat.enemies:
            if not e.is_alive():
                continue
            for status in ("vulnerable", "weak"):
                found = e.get_status(status)
                amounts[e.unit_id, status] = getattr(found, "amount", 0) or 0
            if amounts[e.unit_id, "vulnerable"] > 0:
                shares[e.unit_id] = self._share(e.unit_id, "vulnerable")
        return {"amounts": amounts, "vulnerable": shares}

    def _note(self, results, before):
        """Read one action's results: debuffs on enemies (and whose), Block given, damage
        dealt, and the bonus from the agent's Vulnerable on a teammate's hit. `before`:
        _before_action(), taken just before it."""
        st = self.stats
        enemy_ids = {e.unit_id: e for e in self.combat.enemies}
        amounts, vulnerable = dict(before["amounts"]), before["vulnerable"]
        for r in _flat(results):
            effect, source, target = r.get("effect_id"), r.get("source_id"), r.get("target_id")
            seat = self.seat_of.get(source)
            if seat is None:
                continue
            amount = r.get("amount") or 0
            if effect in ("vulnerable", "weak") and target in enemy_ids:
                # a status's result carries the stacks it now has, so what this added is the
                # difference (none when Artifact took it)
                added = amount - amounts.get((target, effect), 0)
                amounts[target, effect] = amount
                if added > 0:
                    owners = self.owners.setdefault(target, {}).setdefault(effect, {})
                    owners[seat] = owners.get(seat, 0) + added
                    if seat == 0:
                        st["vuln_applied" if effect == "vulnerable" else "weak_applied"] += 1
            elif effect == "instant_block" and target in self.seat_of:
                receiver = self.seat_of[target]
                ally = self.allies[receiver]
                before = (r.get("target_block") or 0) - amount
                need = max(0, self.incoming(receiver) - before)
                st["useful_block"][seat] += min(amount, need) / ally.max_hp
                if seat == 0 and receiver != 0:
                    st["block_to_ally"][receiver] += amount
                    self.agent_block[receiver] += amount
            elif effect == "instant_damage" and target in enemy_ids:
                st["damage"][seat] += amount
                st["kills"][seat] += 1 if r.get("killed") else 0
                share = vulnerable.get(target, 0.0)
                if seat != 0 and share > 0:
                    st["bonus_damage"] += self._vulnerable_bonus(r, self.allies[seat]) * share
                    st["vuln_cashed"] += share

    @staticmethod
    def _vulnerable_bonus(r, attacker):
        """HP this hit took off only because of the target's Vulnerable: the whole swing with
        the multiplier undone (rounded up: the largest hit that would have come out at this
        number), less what the target's Block took."""
        total, hp_lost = r.get("total") or 0, r.get("amount") or 0
        multiplier = Vulnerable.MULTIPLIER
        cruelty = attacker.get_status("cruelty")
        if cruelty is not None:
            multiplier += cruelty.amount / 100
        without = math.ceil(total / multiplier - 1e-9)
        absorbed = max(0, total - hp_lost)
        hp_before = (r.get("target_hp") or 0) + hp_lost
        return max(0, hp_lost - min(hp_before, max(0, without - absorbed)))

    def _sync(self):
        """After every engine action: result, turn, who entered, debuff owners kept to the
        stacks still on each enemy, HP lost and knock-outs; and a new version for the views."""
        c = self.combat
        if c.result is CombatResult.VICTORY:
            self.result = "win"
        elif c.result is CombatResult.DEFEAT:
            self.result = "lose"
        self.turn = c.turn_number
        for enemy in c.enemies:
            self.entered.setdefault(enemy.unit_id, enemy.max_hp)
        self.total_enemy_max_hp = sum(self.entered.values())
        for enemy_id, by_status in self.owners.items():
            enemy = next((e for e in c.enemies if e.unit_id == enemy_id), None)
            for status, owners in by_status.items():
                st = enemy.get_status(status) if enemy is not None and enemy.is_alive() else None
                amount = getattr(st, "amount", 0) or 0
                total = sum(owners.values())
                if amount <= 0:
                    owners.clear()
                elif total > amount:                       # worn off: everyone's share shrinks alike
                    for k in owners:
                        owners[k] *= amount / total
                elif total < amount:                       # from somewhere else (an enemy, a relic)
                    owners[-1] = owners.get(-1, 0) + amount - total
        for i, ally in enumerate(self.allies):
            if ally.current_hp < self._hp[i]:
                self.stats["hp_lost_frac"][i] += (self._hp[i] - ally.current_hp) / ally.max_hp
            if self._alive[i] and not ally.is_alive():
                self.stats["knockouts"] += 1
            self._hp[i], self._alive[i] = ally.current_hp, ally.is_alive()
        self.version += 1
