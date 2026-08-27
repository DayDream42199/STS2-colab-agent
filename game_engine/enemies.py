"""
Enemy model. Enemies telegraph an "intent" (what they'll do next) before
the player acts, matching STS conventions -- important for an RL agent,
since the intent is part of the observable state.
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import List, Callable, Optional
import random

from .entities import Entity, CONTENT_RNG
from .statuses import StatusType
from .cards import (make_wound, make_infection, make_slimed, make_dazed,
                    make_beckon, make_toxic, make_frantic_escape,
                    make_burn, make_wither)


class IntentType(Enum):
    ATTACK = auto()
    ATTACK_DEBUFF = auto()
    DEFEND = auto()
    BUFF = auto()
    DEBUFF = auto()


# CONTENT_RNG is what the HP rolls in the make_*() factories below draw from,
# instead of the global `random` module. It is defined in entities.py -- see
# the long note there for why -- because this module imports that one, so
# that is the only end of the edge both Player and Enemy construction can
# reach. Drivers call entities.seed_content() before building a fight.


# Confirmed from the STS2 Multiplayer wiki page (re-verified, exact
# formulas rather than a guessed lookup table):
#
#   MultiplayerMonsterHP = MonsterHP * PlayerCount * ActScaling
#   MultiplayerBlock     = Block * PlayerCount * ActScaling
#     EXCEPT 2-player Block scaling was nerfed (patch v0.108.0, July 2026)
#     to a flat x2 regardless of Act, instead of following the formula.
#
# ActScaling: Act1=1.1, Act2=1.2, Act3 hallway=1.2, Act3 boss=1.3
#
# Special per-buff scaling (Plating, Artifact, Slippery, Skittish) and
# "general buff" scaling (Regen, Curl Up, Flutter, etc.) use their own
# formulas -- see scale_special_buff() below. Only Plating overlaps with a
# status this replica currently implements (PLATED_ARMOR); the other three
# don't exist as StatusTypes yet, so their formulas are provided but unused
# until those statuses are added.
ACT_SCALING = {"act1": 1.1, "act2": 1.2, "act3": 1.2, "act3boss": 1.3}


def hp_scale_multiplier(player_count: int, act: str = "act1") -> float:
    if player_count <= 1:
        return 1.0
    return player_count * ACT_SCALING.get(act, 1.0)


def block_scale_multiplier(player_count: int, act: str = "act1") -> float:
    if player_count <= 1:
        return 1.0
    if player_count == 2:
        return 2.0   # flat, post-nerf -- NOT act-scaled for 2p specifically
    return player_count * ACT_SCALING.get(act, 1.0)


def scale_special_buff(status_name: str, base_amount: float, player_count: int) -> float:
    """Formulas confirmed on the wiki for enemy buffs that scale differently
    than plain HP/Block. All four now have real StatusTypes AND real enemies
    granting them, so none of these formulas is unexercised scaffolding any
    more: Plating (Sewer Clam), Slippery (Inklet, Vantom), Artifact (Punch
    Construct), Skittish (Phantasmal Gardener)."""
    if player_count <= 1:
        return base_amount
    n = player_count
    if status_name == "plating":       # == PLATED_ARMOR in this replica
        return base_amount * ((n - 1) * 2 + 1)
    if status_name == "artifact":
        return base_amount + (n - 1)
    if status_name == "slippery":      # == SLIPPERY in this replica
        return base_amount * n
    if status_name == "skittish":
        return int(base_amount * ((n - 1) * 0.5 + 1))   # rounds down
    # "general buff" scaling (Regen, Curl Up, Flutter, Hardened Shell,
    # Plow, Rampart, Reattach, Shriek) -- same formula as HP scaling
    return base_amount * hp_scale_multiplier(player_count)


# StatusType -> scale_special_buff() name, for any starting status an enemy
# factory sets (at its base/solo value) directly on the Enemy before
# scale_enemy_for_players() runs. All four are live (the earlier note here
# saying Artifact/Skittish "aren't StatusTypes yet" is obsolete).
# THORNS is deliberately absent: no enemy STARTS with it -- Toadpole gains
# it mid-combat from its Spiken move -- so scale_enemy_for_players() would
# never see it, and inventing a formula for a case that can't occur would
# be guessing. Revisit if an Act 2/3 enemy turns up with starting Thorns.
SPECIAL_BUFF_STATUSES = {
    StatusType.PLATED_ARMOR: "plating",
    StatusType.SLIPPERY: "slippery",
    StatusType.ARTIFACT: "artifact",
    StatusType.SKITTISH: "skittish",
}


def scale_enemy_for_players(enemy: "Enemy", player_count: int, act: str = "act1") -> "Enemy":
    """Apply real STS2 multiplayer HP + Block scaling in place, plus any
    special-buff scaling for starting statuses an enemy factory set at
    its base/solo value (e.g. Inklet's starting 1 Slippery). No-op scaling
    factors for solo (player_count=1) -- scale_special_buff already
    returns base_amount unchanged there, so this is safe to always run.

    Guarded against double-application: this mutates max_hp/statuses IN
    PLACE, so running the same Enemy object through two CombatEngines
    (instead of calling its factory again) would scale it twice into a
    silently over-tuned enemy. Factories are always called fresh in
    practice; this just makes the footgun inert."""
    if getattr(enemy, "_scaled_for_players", False):
        return enemy
    enemy._scaled_for_players = True
    hp_mult = hp_scale_multiplier(player_count, act)
    if hp_mult != 1.0:
        scaled = max(1, round(enemy.max_hp * hp_mult))
        enemy.max_hp = scaled
        enemy.hp = scaled
    enemy.block_scale_mult = block_scale_multiplier(player_count, act)
    for status, name in SPECIAL_BUFF_STATUSES.items():
        base = enemy.get_status(status)
        if base > 0:
            enemy.statuses[status] = round(scale_special_buff(name, base, player_count))
    return enemy


@dataclass
class Move:
    name: str
    intent: IntentType
    # resolve(engine, self_enemy) -> None
    resolve: Callable
    damage: int = 0   # for display / observation purposes (base damage, pre-strength)


class Enemy(Entity):
    def __init__(self, name: str, max_hp: int, moveset: List[Move],
                 choose_move: Callable[["Enemy", int], Move],
                 category: str = "normal"):
        super().__init__(name, max_hp)
        self.moveset = moveset
        self._choose_move = choose_move
        self.current_move: Optional[Move] = None
        self.turn_count = 0
        self.rng = random.Random()
        self.block_scale_mult = 1.0   # set by scale_enemy_for_players()
        # "normal" | "elite" | "boss". Until now the elite/boss distinction
        # existed only as display text in play.py's encounter menus ("Byrdonis
        # (Elite)"), so nothing in the engine could actually branch on it --
        # which is what kept Pantograph ("at the start of each Boss combat")
        # and White Star ("Elites drop an additional Rare card") unportable.
        self.category = category
        # Skittish bookkeeping. hit_by_current_card is set by
        # Entity.take_damage and read once the whole card resolves;
        # skittish_used_this_turn enforces the "first time each turn" limit
        # (Skittish stacks are the block AMOUNT, so they can't be spent to
        # track it the way Slippery's are).
        self.hit_by_current_card = False
        self.skittish_used_this_turn = False
        # --- summoning / minion bookkeeping (see CombatEngine.summon_enemy) ---
        # on_death(engine, self) fires once when this enemy dies, for the
        # "summons reinforcements on death" enemies (Gremlin Merc, Phrog
        # Parasite). death_resolved makes that exactly-once even though
        # _check_victory_defeat runs after every damage source.
        self.on_death: Optional[Callable] = None
        self.death_resolved = False
        self.is_minion = False
        self.leader: Optional["Enemy"] = None
        self.stunned_turns = 0     # skips this many of its own turns
        # Delayed revival (Decimillipede's Reattach: "revives in 2 turns").
        self.revive_in = 0
        self.on_revive: Optional[Callable] = None
        self.invulnerable = False  # Waterfall Giant while it charges Explode
        self.attacked_by_this_turn = []   # Gang Up
        self.knockdown = None             # Knockdown: (caster, multiplier)

    def gain_block(self, amount: int, from_card: bool = True):
        """Overrides Entity.gain_block to apply real STS2 multiplayer
        block scaling (see block_scale_multiplier() above) before the
        normal Frail-etc. multiplier logic in the base class.

        `from_card` is accepted and forwarded purely to keep the signature
        substitutable with the base class -- enemies play no cards, so it
        never changes anything here."""
        return super().gain_block(amount * self.block_scale_mult, from_card)

    def start_combat(self, seed: Optional[int] = None):
        if seed is not None:
            self.rng.seed(seed)
        self.turn_count = 0
        self.current_move = self._choose_move(self, self.turn_count)

    def queue_next_move(self):
        self.turn_count += 1
        self.current_move = self._choose_move(self, self.turn_count)

    def take_turn(self, engine):
        """Mirrors Player.start_turn()/end_turn()'s status bookkeeping around
        the enemy's action. Enemies previously ran NONE of it, so every
        Entity-level status rule silently did nothing on their side:
        Vulnerable/Weak never expired (permanent debuffs), Poison never
        ticked (Twisted Funnel was a dead relic), and enemy Block piled up
        across turns instead of resetting -- Axe Raider just got tankier
        every round.

        Block clears at the START of the enemy's own turn (not the end), so
        block it gained last turn still protects it through the player's
        turn -- the same asymmetry Player.start_turn() already uses, and
        what real STS does. That ordering also means Poison lands on a
        0-Block enemy, so it hits HP directly, matching how Poison already
        behaves on players."""
        # Burrowed (Tunneler): Block survives into its own turn instead of
        # being cleared, which is what makes its 32-Block dig-in stick.
        if not self.has_status(StatusType.BURROWED):
            self.block = 0
        self.skittish_used_this_turn = False
        self.tick_start_of_turn(engine.log)
        if not self.alive:
            # Poison can kill an enemy before it ever acts. Bail out without
            # acting or queueing; run_enemy_turn()'s own _check_victory_defeat
            # picks up the death.
            return

        if self.current_move is None:
            self.current_move = self._choose_move(self, self.turn_count)
        engine.log.append(f"{self.name} uses {self.current_move.name}")
        self.current_move.resolve(engine, self)
        self.queue_next_move()

        self.apply_end_of_turn_gains(engine.log)
        self.decay_statuses_end_of_turn()


# ---------------------------------------------------------------------------
# Concrete enemies
# ---------------------------------------------------------------------------

def _dmg_move(base):
    def _resolve(engine, enemy):
        dmg = enemy.deal_attack_damage(base)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
    return _resolve


# Real STS2 Act 1 ("Overgrowth") trash mobs, replacing the old STS1
# placeholders (Jaw Worm/Cultist/Louse/Acid Slime don't exist in STS2 --
# see README's source-reliability note). HP and move numbers below are
# the wiki.gg-documented "Standard difficulty" values; Ascension-scaled
# variants aren't modeled.

def make_nibbit() -> Enemy:
    """Wiki: HP 42-46. Butt (attack 12); Hesitant Slice (attack 6 + gain 5
    Block); Hiss (buff: gain 2 Strength). Solo opens with Butt, then cycles
    the three moves in a fixed order -- exact cycle order past the opener
    isn't spelled out on the wiki, so Hesitant Slice -> Hiss -> Butt is a
    reasonable fixed loop, not a confirmed sequence."""
    butt = Move("Butt", IntentType.ATTACK, _dmg_move(12), damage=12)

    def _hesitant_slice(engine, enemy):
        dmg = enemy.deal_attack_damage(6)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        enemy.gain_block(5)
    hesitant_slice = Move("Hesitant Slice", IntentType.ATTACK, _hesitant_slice, damage=6)

    def _hiss(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    hiss = Move("Hiss", IntentType.BUFF, _hiss, damage=0)

    cycle = [hesitant_slice, hiss, butt]

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return butt
        return cycle[(turn - 1) % len(cycle)]

    hp = CONTENT_RNG.randint(42, 46)
    return Enemy("Nibbit", hp, [butt, hesitant_slice, hiss], choose)


def make_shrinker_beetle() -> Enemy:
    """Wiki: HP 38-40. Shrinker (debuff: applies Shrink -- attacks deal 30%
    less damage); Chomp (attack 7); Stomp (attack 13). Always opens with
    Shrinker, then alternates Chomp/Stomp.

    Shrink lasts 3 turns per Module:Powers/StS2_data/Debuff. It was applied
    with 1 stack (so 1 turn) on an earlier, conflicting reading."""
    def _shrinker(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.add_status(StatusType.SHRINK, 3, applier=enemy)
        engine.log.append(f"{target.name} is Shrunk for 3 turns ({enemy.name})")
    shrinker = Move("Shrinker", IntentType.DEBUFF, _shrinker, damage=0)
    chomp = Move("Chomp", IntentType.ATTACK, _dmg_move(7), damage=7)
    stomp = Move("Stomp", IntentType.ATTACK, _dmg_move(13), damage=13)

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return shrinker
        return chomp if turn % 2 == 1 else stomp

    hp = CONTENT_RNG.randint(38, 40)
    return Enemy("Shrinker Beetle", hp, [shrinker, chomp, stomp], choose)


def make_fuzzy_wurm_crawler() -> Enemy:
    """Wiki: HP 55-57. 3-turn repeating cycle: Acid Goop (attack 4), Inhale
    (buff: gain 7 Strength), Acid Goop (attack 4) -- Strength persists
    across cycles, so later Acid Goops hit harder."""
    acid_goop = Move("Acid Goop", IntentType.ATTACK, _dmg_move(4), damage=4)

    def _inhale(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 7)
    inhale = Move("Inhale", IntentType.BUFF, _inhale, damage=0)

    cycle = [acid_goop, inhale, acid_goop]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    hp = CONTENT_RNG.randint(55, 57)
    return Enemy("Fuzzy Wurm Crawler", hp, [acid_goop, inhale], choose)


def make_inklet_trio() -> List[Enemy]:
    """Wiki: HP 11-17 each. Always appears in groups of three, each
    starting with 1 stack of Slippery. Jab (3 dmg); Windup Punch (3 hits
    of 2 dmg each); Piercing Gaze (10 dmg). AI: the middle Inklet always
    opens with Windup Punch; the two outer Inklets open with Jab "most
    likely" or Windup Punch (exact odds aren't given on the wiki --
    approximated here as 70/30 Jab/Windup Punch). After the opener: Jab
    is always followed by a random Piercing Gaze/Windup Punch; either of
    those two is always followed by Jab.

    Ported specifically to exercise the Slippery special-buff multiplayer
    scaling (scale_special_buff/SPECIAL_BUFF_STATUSES above) -- no real
    enemy in this replica used it before this, so the formula was
    previously unexercised scaffolding (see README known gaps)."""
    jab = Move("Jab", IntentType.ATTACK, _dmg_move(3), damage=3)

    def _windup_punch(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(3):
            if not target.alive:
                break
            dmg = enemy.deal_attack_damage(2)
            target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
    windup_punch = Move("Windup Punch", IntentType.ATTACK, _windup_punch, damage=2)
    piercing_gaze = Move("Piercing Gaze", IntentType.ATTACK, _dmg_move(10), damage=10)
    moveset = [jab, windup_punch, piercing_gaze]

    def _make_choose(position):
        def choose(enemy: Enemy, turn: int) -> Move:
            if turn == 0:
                if position == "middle":
                    return windup_punch
                return jab if enemy.rng.random() < 0.7 else windup_punch
            if enemy.current_move is jab:
                return enemy.rng.choice([piercing_gaze, windup_punch])
            return jab
        return choose

    inklets = []
    for position in ("outer", "middle", "outer"):
        hp = CONTENT_RNG.randint(11, 17)
        e = Enemy("Inklet", hp, list(moveset), _make_choose(position))
        e.add_status(StatusType.SLIPPERY, 1)
        inklets.append(e)
    return inklets


# ---------------------------------------------------------------------------
# Elite and boss -- real Act 1 ("Overgrowth") encounters. Phrog Parasite
# (the other Overgrowth elite) was passed over for now: its Infect move
# needs its own status-card type (Infection, distinct from Wound) and its
# death effect summons 4 new enemies mid-combat, which this engine's fixed
# enemy list (set once at CombatEngine construction) has no mechanism for.
# ---------------------------------------------------------------------------

def make_byrdonis() -> Enemy:
    """Wiki: HP 81-84. Elite. Starts with 'Territorial 1' -- gains 1
    Strength at the end of its own turn, implemented directly in both
    moves' resolve functions since every one of its turns uses one of
    them (no generic 'end of turn' hook needed for a single enemy).
    Swoop (17 dmg); Peck (3 dmg x3). Fixed alternation, opens with Swoop."""
    def _swoop(engine, enemy):
        dmg = enemy.deal_attack_damage(17)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.STRENGTH, 1)
    swoop = Move("Swoop", IntentType.ATTACK, _swoop, damage=17)

    def _peck(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(3):
            if not target.alive:
                break
            dmg = enemy.deal_attack_damage(3)
            target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.STRENGTH, 1)
    peck = Move("Peck", IntentType.ATTACK, _peck, damage=3)

    cycle = [swoop, peck]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    hp = CONTENT_RNG.randint(81, 84)
    return Enemy("Byrdonis", hp, [swoop, peck], choose, category="elite")


def make_vantom() -> Enemy:
    """Wiki: HP 173 (a single confirmed value, not a range). Boss. Starts
    with 9 Slippery. Fixed 4-move cycle, repeating: Ink Blot (7 dmg);
    Inky Lance (6 dmg x2); Dismember (27 dmg, shuffles 3 Wound cards into
    the target's discard pile); Prepare (gain 2 Strength)."""
    ink_blot = Move("Ink Blot", IntentType.ATTACK, _dmg_move(7), damage=7)

    def _inky_lance(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(2):
            if not target.alive:
                break
            dmg = enemy.deal_attack_damage(6)
            target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
    inky_lance = Move("Inky Lance", IntentType.ATTACK, _inky_lance, damage=6)

    def _dismember(engine, enemy):
        target = engine.pick_enemy_attack_target()
        dmg = enemy.deal_attack_damage(27)
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        if target.alive:
            for _ in range(3):
                target.discard_pile.append(make_wound())
            engine.log.append(f"{target.name} has 3 Wounds shuffled into their discard pile ({enemy.name})")
    dismember = Move("Dismember", IntentType.ATTACK_DEBUFF, _dismember, damage=27)

    def _prepare(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    prepare = Move("Prepare", IntentType.BUFF, _prepare, damage=0)

    cycle = [ink_blot, inky_lance, dismember, prepare]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    vantom = Enemy("Vantom", 173, [ink_blot, inky_lance, dismember, prepare], choose,
                    category="boss")
    vantom.add_status(StatusType.SLIPPERY, 9)
    return vantom


# ---------------------------------------------------------------------------
# Remaining real Act 1 ("Overgrowth") normal monsters -- HP and move data
# from the wiki's raw Module:Enemies/StS2_data/Overgrowth page. Where the
# wiki gives no explicit opener/cycle order (most of these), a fixed
# reasonable loop is used and called out per-enemy, same disclosure
# discipline as Nibbit's existing docstring. Fogmog's third real move
# (Illusory Spores, "summons an Eye With Teeth") is left out -- mid-combat
# enemy summoning has no engine support (same blocker as Phrog Parasite,
# see README).
# ---------------------------------------------------------------------------

def _shuffle_status_cards(engine, target, factory, count, label):
    for _ in range(count):
        target.discard_pile.append(factory())
    engine.log.append(f"{target.name} has {count} {label} shuffled into their discard pile")


# --- Ruby Raiders (each usable solo or grouped) ---

def make_assassin_raider() -> Enemy:
    """Wiki: HP 18-23. Single move: Killshot (10 dmg)."""
    killshot = Move("Killshot", IntentType.ATTACK, _dmg_move(10), damage=10)

    def choose(enemy: Enemy, turn: int) -> Move:
        return killshot

    hp = CONTENT_RNG.randint(18, 23)
    return Enemy("Assassin Raider", hp, [killshot], choose)


def make_axe_raider() -> Enemy:
    """Wiki: HP 20-22. Swing (5 dmg, gain 5 Block); Big Swing (12 dmg).
    No confirmed cycle order -- opens with Swing, alternates."""
    def _swing(engine, enemy):
        dmg = enemy.deal_attack_damage(5)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        enemy.gain_block(5)
    swing = Move("Swing", IntentType.ATTACK, _swing, damage=5)
    big_swing = Move("Big Swing", IntentType.ATTACK, _dmg_move(12), damage=12)
    cycle = [swing, big_swing]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    hp = CONTENT_RNG.randint(20, 22)
    return Enemy("Axe Raider", hp, [swing, big_swing], choose)


def make_brute_raider() -> Enemy:
    """Wiki: HP 30-33. Beat (7 dmg); Clap (gain 3 Strength). No confirmed
    cycle order -- opens with Beat, alternates."""
    beat = Move("Beat", IntentType.ATTACK, _dmg_move(7), damage=7)

    def _clap(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 3)
    clap = Move("Clap", IntentType.BUFF, _clap, damage=0)
    cycle = [beat, clap]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    hp = CONTENT_RNG.randint(30, 33)
    return Enemy("Brute Raider", hp, [beat, clap], choose)


def make_crossbow_raider() -> Enemy:
    """Wiki: HP 18-21. Reload (gain 3 Block); Fire! (14 dmg). Opens with
    Reload (thematically loads before firing), alternates."""
    def _reload(engine, enemy):
        enemy.gain_block(3)
    reload_ = Move("Reload", IntentType.DEFEND, _reload, damage=0)
    fire = Move("Fire!", IntentType.ATTACK, _dmg_move(14), damage=14)
    cycle = [reload_, fire]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    hp = CONTENT_RNG.randint(18, 21)
    return Enemy("Crossbow Raider", hp, [reload_, fire], choose)


def make_tracker_raider() -> Enemy:
    """Wiki: HP 21-25. Track (apply 2 Frail); Unleash the Hounds (1 dmg
    x8). No confirmed cycle order -- opens with Track, alternates."""
    def _track(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.add_status(StatusType.FRAIL, 2)
        engine.log.append(f"{target.name} gains 2 Frail ({enemy.name})")
    track = Move("Track", IntentType.DEBUFF, _track, damage=0)

    def _unleash(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(8):
            if not target.alive:
                break
            dmg = enemy.deal_attack_damage(1)
            target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
    unleash = Move("Unleash the Hounds", IntentType.ATTACK, _unleash, damage=1)
    cycle = [track, unleash]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    hp = CONTENT_RNG.randint(21, 25)
    return Enemy("Tracker Raider", hp, [track, unleash], choose)


# --- Solo/paired encounters ---

def make_cubex_construct() -> Enemy:
    """Wiki: HP 65. Charge Up (gain 2 Strength); Repeater Blast (7 dmg,
    gain 2 Strength); Expel Blast (5 dmg x2). Opens with Charge Up
    (thematic), then cycles Repeater Blast/Expel Blast -- no confirmed
    full cycle order."""
    def _charge_up(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    charge_up = Move("Charge Up", IntentType.BUFF, _charge_up, damage=0)

    def _repeater_blast(engine, enemy):
        dmg = enemy.deal_attack_damage(7)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.STRENGTH, 2)
    repeater_blast = Move("Repeater Blast", IntentType.ATTACK, _repeater_blast, damage=7)

    def _expel_blast(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(2):
            if not target.alive:
                break
            dmg = enemy.deal_attack_damage(5)
            target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
    expel_blast = Move("Expel Blast", IntentType.ATTACK, _expel_blast, damage=5)

    cycle = [repeater_blast, expel_blast]

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return charge_up
        return cycle[(turn - 1) % len(cycle)]

    return Enemy("Cubex Construct", 65, [charge_up, repeater_blast, expel_blast], choose)


def make_fogmog() -> Enemy:
    """Wiki: HP 74. Thwack (8 dmg, gain 1 Strength); Headbutt (14 dmg);
    Illusory Spores (summons an Eye With Teeth).

    Illusory Spores was cut from the original port for lack of mid-combat
    summoning and is now restored, so this enemy is finally complete. No
    confirmed cycle order -- the three-move loop below is a guess, same
    caveat as the rest of the region."""
    def _thwack(engine, enemy):
        dmg = enemy.deal_attack_damage(8)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.STRENGTH, 1)
    thwack = Move("Thwack", IntentType.ATTACK, _thwack, damage=8)
    headbutt = Move("Headbutt", IntentType.ATTACK, _dmg_move(14), damage=14)

    def _illusory_spores(engine, enemy):
        engine.summon_enemy(make_eye_with_teeth(), summoner=enemy)
    spores = Move("Illusory Spores", IntentType.BUFF, _illusory_spores, damage=0)
    cycle = [thwack, spores, headbutt]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    return Enemy("Fogmog", 74, cycle, choose)


def make_mawler() -> Enemy:
    """Wiki: HP 72. Rip and Tear (14 dmg); Roar (apply 3 Vulnerable);
    Claw (4 dmg x2). No confirmed cycle order -- opens with Roar
    (debuff-first opener, matching the existing Shrinker Beetle
    precedent), then alternates Rip and Tear/Claw."""
    rip_and_tear = Move("Rip and Tear", IntentType.ATTACK, _dmg_move(14), damage=14)

    def _roar(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.add_status(StatusType.VULNERABLE, 3)
        engine.log.append(f"{target.name} gains 3 Vulnerable ({enemy.name})")
    roar = Move("Roar", IntentType.DEBUFF, _roar, damage=0)

    def _claw(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(2):
            if not target.alive:
                break
            dmg = enemy.deal_attack_damage(4)
            target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
    claw = Move("Claw", IntentType.ATTACK, _claw, damage=4)

    cycle = [rip_and_tear, claw]

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return roar
        return cycle[(turn - 1) % len(cycle)]

    return Enemy("Mawler", 72, [rip_and_tear, roar, claw], choose)


def make_vine_shambler() -> Enemy:
    """Wiki: HP 61. Swipe (6 dmg x2); Grasping Vines (8 dmg, apply 1
    Tangled); Chomp (16 dmg). Tangled is a real STS2 debuff already
    tracked as a StatusType but not yet wired to any effect (needs the
    dynamic-cost-modifier system -- see statuses.py/README known gaps),
    so applying it here is accurate to the wiki but currently inert, same
    as everywhere else Tangled shows up. No confirmed cycle order --
    opens with Swipe, cycles through all three."""
    def _swipe(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(2):
            if not target.alive:
                break
            dmg = enemy.deal_attack_damage(6)
            target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
    swipe = Move("Swipe", IntentType.ATTACK, _swipe, damage=6)

    def _grasping_vines(engine, enemy):
        dmg = enemy.deal_attack_damage(8)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        target.add_status(StatusType.TANGLED, 1)
    grasping_vines = Move("Grasping Vines", IntentType.ATTACK_DEBUFF, _grasping_vines, damage=8)
    chomp = Move("Chomp", IntentType.ATTACK, _dmg_move(16), damage=16)

    cycle = [swipe, grasping_vines, chomp]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    return Enemy("Vine Shambler", 61, [swipe, grasping_vines, chomp], choose)


# --- Biological enemies ---

def make_flyconid() -> Enemy:
    """Wiki: HP 47-49. Weakening Spores (apply 2 Vulnerable); Frail
    Spores (8 dmg, apply 2 Frail); Smash (11 dmg). No confirmed cycle
    order -- opens with Weakening Spores (debuff-first, matching Shrinker
    Beetle), then alternates the other two."""
    def _weakening_spores(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.add_status(StatusType.VULNERABLE, 2)
        engine.log.append(f"{target.name} gains 2 Vulnerable ({enemy.name})")
    weakening_spores = Move("Weakening Spores", IntentType.DEBUFF, _weakening_spores, damage=0)

    def _frail_spores(engine, enemy):
        dmg = enemy.deal_attack_damage(8)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        target.add_status(StatusType.FRAIL, 2)
    frail_spores = Move("Frail Spores", IntentType.ATTACK_DEBUFF, _frail_spores, damage=8)
    smash = Move("Smash", IntentType.ATTACK, _dmg_move(11), damage=11)

    cycle = [frail_spores, smash]

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return weakening_spores
        return cycle[(turn - 1) % len(cycle)]

    hp = CONTENT_RNG.randint(47, 49)
    return Enemy("Flyconid", hp, [weakening_spores, frail_spores, smash], choose)


def make_slithering_strangler() -> Enemy:
    """Wiki: HP 53-55. Constrict (apply 3 Constrict -- 'while the
    Slithering Strangler is alive, take N damage at the end of your
    turn', resolved by CombatEngine._resolve_constrict each turn, not a
    per-move effect here); Thwack (7 dmg, gain 5 Block); Lash (12 dmg).
    No confirmed cycle order -- opens with Constrict (debuff-first),
    alternates the other two."""
    def _constrict(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.add_status(StatusType.CONSTRICT, 3)
        engine.log.append(f"{target.name} gains 3 Constrict ({enemy.name})")
    constrict = Move("Constrict", IntentType.DEBUFF, _constrict, damage=0)

    def _thwack(engine, enemy):
        dmg = enemy.deal_attack_damage(7)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        enemy.gain_block(5)
    thwack = Move("Thwack", IntentType.ATTACK, _thwack, damage=7)
    lash = Move("Lash", IntentType.ATTACK, _dmg_move(12), damage=12)

    cycle = [thwack, lash]

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return constrict
        return cycle[(turn - 1) % len(cycle)]

    hp = CONTENT_RNG.randint(53, 55)
    return Enemy("Slithering Strangler", hp, [constrict, thwack, lash], choose)


def make_snapping_jaxfruit() -> Enemy:
    """Wiki: HP 31-33. Single move: Energy Orb (3 dmg, gain 2 Strength)."""
    def _energy_orb(engine, enemy):
        dmg = enemy.deal_attack_damage(3)
        target = engine.pick_enemy_attack_target()
        target.take_damage(dmg, log=engine.log, label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.STRENGTH, 2)
    energy_orb = Move("Energy Orb", IntentType.ATTACK, _energy_orb, damage=3)

    def choose(enemy: Enemy, turn: int) -> Move:
        return energy_orb

    hp = CONTENT_RNG.randint(31, 33)
    return Enemy("Snapping Jaxfruit", hp, [energy_orb], choose)


# --- Slimes (shuffle Slimed status cards -- a PLAYABLE status card,
# unlike Wound/Infection; see make_slimed()'s docstring in cards.py) ---

def make_leaf_slime_small() -> Enemy:
    """Wiki: HP 11-15. Tackle (3 dmg); Goop (shuffle 1 Slimed). No
    confirmed cycle order -- opens with Goop (status-first, matching the
    classic STS Slime pattern), alternates."""
    tackle = Move("Tackle", IntentType.ATTACK, _dmg_move(3), damage=3)

    def _goop(engine, enemy):
        target = engine.pick_enemy_attack_target()
        _shuffle_status_cards(engine, target, make_slimed, 1, "Slimed")
    goop = Move("Goop", IntentType.DEBUFF, _goop, damage=0)
    cycle = [tackle, goop]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[(turn + 1) % len(cycle)]   # opens with Goop (index 1 at turn 0)

    hp = CONTENT_RNG.randint(11, 15)
    return Enemy("Leaf Slime (S)", hp, [tackle, goop], choose)


def make_leaf_slime_medium() -> Enemy:
    """Wiki: HP 32-35. Clump Shot (8 dmg); Sticky Shot (shuffle 2
    Slimed). No confirmed cycle order -- opens with Sticky Shot,
    alternates."""
    clump_shot = Move("Clump Shot", IntentType.ATTACK, _dmg_move(8), damage=8)

    def _sticky_shot(engine, enemy):
        target = engine.pick_enemy_attack_target()
        _shuffle_status_cards(engine, target, make_slimed, 2, "Slimed")
    sticky_shot = Move("Sticky Shot", IntentType.DEBUFF, _sticky_shot, damage=0)
    cycle = [clump_shot, sticky_shot]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[(turn + 1) % len(cycle)]

    hp = CONTENT_RNG.randint(32, 35)
    return Enemy("Leaf Slime (M)", hp, [clump_shot, sticky_shot], choose)


def make_twig_slime_small() -> Enemy:
    """Wiki: HP 7-11. Single move: Tackle (4 dmg)."""
    tackle = Move("Tackle", IntentType.ATTACK, _dmg_move(4), damage=4)

    def choose(enemy: Enemy, turn: int) -> Move:
        return tackle

    hp = CONTENT_RNG.randint(7, 11)
    return Enemy("Twig Slime (S)", hp, [tackle], choose)


def make_twig_slime_medium() -> Enemy:
    """Wiki: HP 26-28. Chomp (11 dmg); Sticky Shot (shuffle 1 Slimed). No
    confirmed cycle order -- opens with Sticky Shot, alternates."""
    chomp = Move("Chomp", IntentType.ATTACK, _dmg_move(11), damage=11)

    def _sticky_shot(engine, enemy):
        target = engine.pick_enemy_attack_target()
        _shuffle_status_cards(engine, target, make_slimed, 1, "Slimed")
    sticky_shot = Move("Sticky Shot", IntentType.DEBUFF, _sticky_shot, damage=0)
    cycle = [chomp, sticky_shot]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[(turn + 1) % len(cycle)]

    hp = CONTENT_RNG.randint(26, 28)
    return Enemy("Twig Slime (M)", hp, [chomp, sticky_shot], choose)


# --- Minor enemies ---

def make_wriggler() -> Enemy:
    """Wiki: HP 17-21. Nasty Bite (6 dmg); Wriggle (shuffle 1 Infection,
    gain 2 Strength). No confirmed cycle order -- opens with Wriggle
    (status/buff-first), alternates. Also the real spawn of Phrog
    Parasite's death effect (deferred, see README) -- ported standalone
    here so it's independently usable/testable regardless."""
    nasty_bite = Move("Nasty Bite", IntentType.ATTACK, _dmg_move(6), damage=6)

    def _wriggle(engine, enemy):
        target = engine.pick_enemy_attack_target()
        _shuffle_status_cards(engine, target, make_infection, 1, "Infection")
        enemy.add_status(StatusType.STRENGTH, 2)
    wriggle = Move("Wriggle", IntentType.DEBUFF, _wriggle, damage=0)
    cycle = [nasty_bite, wriggle]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[(turn + 1) % len(cycle)]

    hp = CONTENT_RNG.randint(17, 21)
    return Enemy("Wriggler", hp, [nasty_bite, wriggle], choose)


# ===========================================================================
# UNDERDOCKS -- the OTHER Act 1 region. STS2 picks randomly between
# Overgrowth (above) and Underdocks at the start of a run; only Overgrowth
# was ported until now, so roughly half of Act 1 was missing without that
# being written down anywhere.
#
# This is a partial port: the enemies below are the ones buildable from
# mechanics this engine has (plus Skittish, Artifact, and now Thorns, each
# added alongside the enemy that needed it).
# Deliberately NOT ported yet, and why -- see README known gaps:
#   Living Fog      -- "Smoggy" (undocumented on the wiki) + summons Gas Bomb
#   Corpse Slug     -- "Ravenous" (undocumented)
#   Fossil Stalker  -- "Suck" (undocumented)
#   Gremlin Merc    -- "Surprise"/"Thievery" (undocumented; Thievery needs gold)
#   Fat/Sneaky Gremlin, Gas Bomb -- Minions, need mid-combat summoning
#   Two-Tailed Rat  -- "Call for Backup", needs summoning
# As with Overgrowth, the wiki gives no move order for these, so each fixed
# cycle below is a reasonable loop rather than a confirmed sequence.
# ===========================================================================

def _make_cultist(name: str, hp_range, ritual_amount: int, strike_damage: int) -> Enemy:
    """Calcified and Damp Cultist share a moveset and differ only in
    numbers: Incantation (gain N Ritual) then Dark Strike (deal N damage).
    Ritual is already modeled (grants Strength at the start of each of the
    holder's turns), and now actually FIRES on enemies since the enemy
    per-turn tick fix -- before that, a Cultist's whole gimmick would have
    done nothing. Opens with Incantation, as its STS1 namesake does."""
    def _incantation(engine, enemy):
        enemy.add_status(StatusType.RITUAL, ritual_amount)
        engine.log.append(f"{enemy.name} gains {ritual_amount} Ritual")
    incantation = Move("Incantation", IntentType.BUFF, _incantation, damage=0)
    dark_strike = Move("Dark Strike", IntentType.ATTACK, _dmg_move(strike_damage),
                        damage=strike_damage)

    def choose(enemy: Enemy, turn: int) -> Move:
        return incantation if turn == 0 else dark_strike

    return Enemy(name, CONTENT_RNG.randint(*hp_range), [incantation, dark_strike], choose)


def make_calcified_cultist() -> Enemy:
    """Wiki: HP 38-41. Incantation (gain 2 Ritual); Dark Strike (9 dmg)."""
    return _make_cultist("Calcified Cultist", (38, 41), 2, 9)


def make_damp_cultist() -> Enemy:
    """Wiki: HP 51-53. Incantation (gain 5 Ritual); Dark Strike (1 dmg).
    Far more Ritual but a token attack -- it snowballs Strength instead of
    hitting hard early."""
    return _make_cultist("Damp Cultist", (51, 53), 5, 1)


def make_seapunk() -> Enemy:
    """Wiki: HP 44-46. Sea Kick (11 dmg); Spinning Kick (2 dmg x4);
    Bubble Burp (gain 7 Block and 1 Strength)."""
    sea_kick = Move("Sea Kick", IntentType.ATTACK, _dmg_move(11), damage=11)

    def _spinning_kick(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(4):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(2), log=engine.log, label=enemy.name, attacker=enemy)
    spinning_kick = Move("Spinning Kick", IntentType.ATTACK, _spinning_kick, damage=2)

    def _bubble_burp(engine, enemy):
        enemy.gain_block(7)
        enemy.add_status(StatusType.STRENGTH, 1)
    bubble_burp = Move("Bubble Burp", IntentType.DEFEND, _bubble_burp, damage=0)

    cycle = [sea_kick, spinning_kick, bubble_burp]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    return Enemy("Seapunk", CONTENT_RNG.randint(44, 46),
                  [sea_kick, spinning_kick, bubble_burp], choose)


def make_sludge_spinner() -> Enemy:
    """Wiki: HP 37-39. Oil Spray (8 dmg, apply 1 Weak); Slam (11 dmg);
    Rage (6 dmg, gain 3 Strength)."""
    def _oil_spray(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(8), log=engine.log, label=enemy.name, attacker=enemy)
        target.add_status(StatusType.WEAK, 1)
    oil_spray = Move("Oil Spray", IntentType.ATTACK_DEBUFF, _oil_spray, damage=8)
    slam = Move("Slam", IntentType.ATTACK, _dmg_move(11), damage=11)

    def _rage(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(6), log=engine.log, label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.STRENGTH, 3)
    rage = Move("Rage", IntentType.ATTACK, _rage, damage=6)

    cycle = [oil_spray, slam, rage]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    return Enemy("Sludge Spinner", CONTENT_RNG.randint(37, 39), [oil_spray, slam, rage], choose)


def make_sewer_clam() -> Enemy:
    """Wiki: HP 56, starts with Plating 8. Jet (10 dmg); Pressurize (gain 4
    Strength). The first REAL user of enemy Plating -- the special-buff
    scaling for it existed and was tested only synthetically until now."""
    jet = Move("Jet", IntentType.ATTACK, _dmg_move(10), damage=10)

    def _pressurize(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 4)
    pressurize = Move("Pressurize", IntentType.BUFF, _pressurize, damage=0)

    cycle = [jet, pressurize]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    clam = Enemy("Sewer Clam", 56, [jet, pressurize], choose)
    clam.add_status(StatusType.PLATED_ARMOR, 8)
    return clam


def make_punch_construct() -> Enemy:
    """Wiki: HP 55, starts with Artifact 1. READY (gain 10 Block); Fast
    Punch (5 dmg x2, apply 1 Frail); Strong Punch (14 dmg). Opens with
    READY (it 'readies' first), then alternates the punches."""
    def _ready(engine, enemy):
        enemy.gain_block(10)
    ready = Move("READY", IntentType.DEFEND, _ready, damage=0)

    def _fast_punch(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(2):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(5), log=engine.log, label=enemy.name, attacker=enemy)
        target.add_status(StatusType.FRAIL, 1)
    fast_punch = Move("Fast Punch", IntentType.ATTACK_DEBUFF, _fast_punch, damage=5)
    strong_punch = Move("Strong Punch", IntentType.ATTACK, _dmg_move(14), damage=14)

    punches = [fast_punch, strong_punch]

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return ready
        return punches[(turn - 1) % len(punches)]

    construct = Enemy("Punch Construct", 55, [ready, fast_punch, strong_punch], choose)
    construct.add_status(StatusType.ARTIFACT, 1)
    return construct


def make_haunted_ship() -> Enemy:
    """Wiki: HP 63. Haunt (shuffle 5 Dazed into your discard pile, apply 3
    Weak); Swipe (13 dmg); Stomp (4 dmg x3). Opens with Haunt."""
    def _haunt(engine, enemy):
        target = engine.pick_enemy_attack_target()
        _shuffle_status_cards(engine, target, make_dazed, 5, "Dazed")
        target.add_status(StatusType.WEAK, 3)
    haunt = Move("Haunt", IntentType.DEBUFF, _haunt, damage=0)
    swipe = Move("Swipe", IntentType.ATTACK, _dmg_move(13), damage=13)

    def _stomp(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(3):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(4), log=engine.log, label=enemy.name, attacker=enemy)
    stomp = Move("Stomp", IntentType.ATTACK, _stomp, damage=4)

    attacks = [swipe, stomp]

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return haunt
        return attacks[(turn - 1) % len(attacks)]

    return Enemy("Haunted Ship", 63, [haunt, swipe, stomp], choose)


def make_toadpole(start_offset: int = 0) -> Enemy:
    """Wiki: HP 21-25. Fixed cycle, and this one IS confirmed rather than
    invented like most of the others in this region: Whirl (7 dmg) ->
    Spiken (gain 2 Thorns) -> Spike Spit (3 dmg x3, remove 2 Thorns from
    self).

    The only enemy in Act 1 that grants Thorns, and the reason Thorns had
    to fire per-hit rather than per-card: its own 3-hit Spike Spit is the
    tell that the designers expect multi-hit attacks to eat the retaliation
    once per hit. Spike Spit stripping the Thorns it just spent a turn
    gaining is also why Thorns can't be a spend-per-trigger Counter -- see
    the note in statuses.py's STATUS_META.

    start_offset shifts where in the cycle this one begins, for the
    "Toadpoles (Weak)" encounter where the front Toadpole opens on Spiken.
    """
    whirl = Move("Whirl", IntentType.ATTACK, _dmg_move(7), damage=7)

    def _spiken(engine, enemy):
        enemy.add_status(StatusType.THORNS, 2)
        engine.log.append(f"{enemy.name} gains 2 Thorns")
    spiken = Move("Spiken", IntentType.BUFF, _spiken, damage=0)

    def _spike_spit(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(3):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(3), log=engine.log,
                                label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.THORNS, -2)
        engine.log.append(f"{enemy.name} loses 2 Thorns (Spike Spit)")
    spike_spit = Move("Spike Spit", IntentType.ATTACK, _spike_spit, damage=3)

    cycle = [whirl, spiken, spike_spit]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[(turn + start_offset) % len(cycle)]

    return Enemy("Toadpole", CONTENT_RNG.randint(21, 25), list(cycle), choose)


def make_toadpole_pair() -> List[Enemy]:
    """Wiki encounter "Toadpoles (Weak)": Toadpole x2, with the FRONT one
    starting on Spiken instead of Whirl -- so it is already sitting on 2
    Thorns by the time most decks get to swing twice."""
    return [make_toadpole(start_offset=1), make_toadpole(start_offset=0)]


def make_phantasmal_gardener_group() -> List[Enemy]:
    """Wiki: HP 26-31 each, Skittish 6 each, and they fight as FOUR.
    Cycle: Bite (5 dmg) / Lash (7 dmg) / Flail (1 dmg x3) / Enlarge (gain 2
    Strength) -- and the wiki is specific that each Gardener starts at a
    different point in that cycle so they never share a move on the same
    turn, which is modeled below by offsetting each one's start index.

    The only enemy anywhere that grants Skittish, which is why it gates the
    useful half of that status being implemented at all."""
    bite = Move("Bite", IntentType.ATTACK, _dmg_move(5), damage=5)
    lash = Move("Lash", IntentType.ATTACK, _dmg_move(7), damage=7)

    def _flail(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(3):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(1), log=engine.log, label=enemy.name, attacker=enemy)
    flail = Move("Flail", IntentType.ATTACK, _flail, damage=1)

    def _enlarge(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    enlarge = Move("Enlarge", IntentType.BUFF, _enlarge, damage=0)

    cycle = [bite, lash, flail, enlarge]

    def _make_choose(offset):
        def choose(enemy: Enemy, turn: int) -> Move:
            return cycle[(turn + offset) % len(cycle)]
        return choose

    gardeners = []
    for offset in range(4):
        g = Enemy("Phantasmal Gardener", CONTENT_RNG.randint(26, 31),
                   list(cycle), _make_choose(offset), category="elite")
        g.add_status(StatusType.SKITTISH, 6)
        gardeners.append(g)
    return gardeners


# ===========================================================================
# THE REST OF ACT 1 -- remaining elites, bosses, and the summon-only
# minions that mid-combat summoning finally made portable.
#
# Regional layout, corrected against the wiki's Elites/Bosses data modules.
# This project previously had Ceremonial Beast filed as an elite and Phrog
# Parasite as a normal monster. Both were wrong:
#   Overgrowth elites: Byrdonis, Bygone Effigy, Phrog Parasite
#   Overgrowth bosses: Vantom, Ceremonial Beast, The Kin
#   Underdocks elites: Phantasmal Gardener, Skulking Colony, Terror Eel
#   Underdocks bosses: Lagavulin Matriarch, Soul Fysh, Waterfall Giant
# ===========================================================================

def _nothing(engine, enemy):
    """A move that does nothing (Sleep / Stun / Spawned). Modeled as a real
    move rather than a skipped turn so the intent stays visible to the
    player, which is the entire point of a telegraphed sleep."""
    return


def make_eye_with_teeth() -> Enemy:
    """Wiki: Minion, HP 6. Distract (shuffles 3 Dazed into your discard
    pile). Summoned by Fogmog; unportable until summoning existed."""
    def _distract(engine, enemy):
        target = engine.pick_enemy_attack_target()
        _shuffle_status_cards(engine, target, make_dazed, 3, "Dazed")
    distract = Move("Distract", IntentType.DEBUFF, _distract, damage=0)
    e = Enemy("Eye With Teeth", 6, [distract], lambda en, t: distract)
    e.is_minion = True
    return e


def make_bygone_effigy() -> Enemy:
    """Wiki: Elite, HP 127. Sleep (does nothing) -> Wake (gains 10
    Strength) -> Slashes (13 damage) every turn thereafter.

    The wiki describes a fixed sequence and does NOT say damage wakes it
    early, so this is a scripted opener rather than a Lagavulin-style
    "wakes when hit". Noted because the STS1 instinct is the opposite."""
    sleep = Move("Sleep", IntentType.BUFF, _nothing, damage=0)

    def _wake(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 10)
        engine.log.append(f"{enemy.name} wakes up and gains 10 Strength")
    wake = Move("Wake", IntentType.BUFF, _wake, damage=0)
    slashes = Move("Slashes", IntentType.ATTACK, _dmg_move(13), damage=13)

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return sleep
        if turn == 1:
            return wake
        return slashes

    return Enemy("Bygone Effigy", 127, [sleep, wake, slashes], choose, category="elite")


def make_phrog_parasite() -> Enemy:
    """Wiki: Elite, HP 61-64. Alternates Infect (shuffles 3 Infection) and
    Lash (4 damage x4). Its "Infested" power spawns 4 Wrigglers when it
    DIES -- the reason this elite stayed unported until summoning existed.
    The Wrigglers arrive Stunned, matching the wiki's note that they take
    no action on the turn they appear."""
    def _infect(engine, enemy):
        target = engine.pick_enemy_attack_target()
        _shuffle_status_cards(engine, target, make_infection, 3, "Infection")
    infect = Move("Infect", IntentType.DEBUFF, _infect, damage=0)

    def _lash(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(4):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(4), log=engine.log,
                                label=enemy.name, attacker=enemy)
    lash = Move("Lash", IntentType.ATTACK, _lash, damage=4)
    cycle = [infect, lash]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    def _infested(engine, enemy):
        engine.summon_enemy([make_wriggler() for _ in range(4)],
                             summoner=enemy, stunned=True)

    e = Enemy("Phrog Parasite", CONTENT_RNG.randint(61, 64), cycle, choose, category="elite")
    e.on_death = _infested
    return e


def make_ceremonial_beast() -> Enemy:
    """Wiki: Boss, HP 252, two phases.

    Phase 1: Stamp (gains Plow 150) on turn 1, then Plow (18 damage, gains
    2 Strength) every turn. Phase 2 starts the first time its HP drops to
    150 or below: it is Stunned for a turn and LOSES ALL STRENGTH, then
    cycles Beast Cry (applies 1 Ringing) / Stomp (15) / Crush (17, gains 3
    Strength).

    The threshold is checked when it picks its next move rather than the
    instant HP crosses it. Observably the same -- either way the Stun eats
    its next turn -- and it keeps the phase logic in one place instead of
    hooking the damage pipeline for a single boss."""
    def _stamp(engine, enemy):
        enemy.add_status(StatusType.PLOW, 150)
        engine.log.append(f"{enemy.name} gains Plow 150 (phase 2 at 150 HP)")
    stamp = Move("Stamp", IntentType.BUFF, _stamp, damage=0)

    def _plow(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(18), log=engine.log,
                            label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.STRENGTH, 2)
    plow = Move("Plow", IntentType.ATTACK, _plow, damage=18)
    stun = Move("Stun", IntentType.BUFF, _nothing, damage=0)

    def _beast_cry(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.RINGING, 1, applier=enemy)
        engine.log.append(f"{enemy.name} applies 1 Ringing (only 1 card next turn)")
    beast_cry = Move("Beast Cry", IntentType.DEBUFF, _beast_cry, damage=0)
    stomp = Move("Stomp", IntentType.ATTACK, _dmg_move(15), damage=15)

    def _crush(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(17), log=engine.log,
                            label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.STRENGTH, 3)
    crush = Move("Crush", IntentType.ATTACK, _crush, damage=17)
    phase2 = [beast_cry, stomp, crush]

    def choose(enemy: Enemy, turn: int) -> Move:
        threshold = enemy.get_status(StatusType.PLOW)
        broken = getattr(enemy, "plow_broken", False)
        if threshold and not broken and enemy.hp <= threshold:
            enemy.plow_broken = True
            enemy.phase2_turn = 0
            enemy.statuses.pop(StatusType.STRENGTH, None)
            return stun
        if broken:
            i = getattr(enemy, "phase2_turn", 0)
            enemy.phase2_turn = i + 1
            return phase2[i % len(phase2)]
        return stamp if turn == 0 else plow

    return Enemy("Ceremonial Beast", 252, [stamp, plow, stun] + phase2,
                  choose, category="boss")


def make_the_kin() -> List[Enemy]:
    """Wiki: Overgrowth boss "The Kin" -- one Kin Priest (190 HP) and TWO
    Kin Followers (58-59 each), all present from the start rather than
    summoned. The followers start offset: one opens on Quick Slash, the
    other on Power Dance.

    The Followers have the Minion power ("minions abandon combat without
    their leader"), so killing the Priest ends the fight outright --
    handled generically by CombatEngine.handle_enemy_death()."""
    def _orb(name, dmg, status, amount):
        def _resolve(engine, enemy):
            target = engine.pick_enemy_attack_target()
            target.take_damage(enemy.deal_attack_damage(dmg), log=engine.log,
                                label=enemy.name, attacker=enemy)
            target.add_status(status, amount, applier=enemy)
        return Move(name, IntentType.ATTACK, _resolve, damage=dmg)

    orb_frailty = _orb("Orb of Frailty", 8, StatusType.FRAIL, 1)
    orb_weakness = _orb("Orb of Weakness", 8, StatusType.WEAK, 1)

    def _soul_beam(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(3):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(3), log=engine.log,
                                label=enemy.name, attacker=enemy)
    soul_beam = Move("Soul Beam", IntentType.ATTACK, _soul_beam, damage=3)

    def _dark_ritual(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    dark_ritual = Move("Dark Ritual", IntentType.BUFF, _dark_ritual, damage=0)

    priest_cycle = [orb_frailty, orb_weakness, soul_beam, dark_ritual]

    def priest_choose(enemy: Enemy, turn: int) -> Move:
        return priest_cycle[turn % len(priest_cycle)]

    priest = Enemy("Kin Priest", 190, list(priest_cycle), priest_choose, category="boss")

    quick_slash = Move("Quick Slash", IntentType.ATTACK, _dmg_move(5), damage=5)

    def _boomerang(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(2):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(2), log=engine.log,
                                label=enemy.name, attacker=enemy)
    boomerang = Move("Boomerang", IntentType.ATTACK, _boomerang, damage=2)

    def _power_dance(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    power_dance = Move("Power Dance", IntentType.BUFF, _power_dance, damage=0)

    follower_cycle = [quick_slash, boomerang, power_dance]

    def _make_follower_choose(offset):
        def choose(enemy: Enemy, turn: int) -> Move:
            return follower_cycle[(turn + offset) % len(follower_cycle)]
        return choose

    units = [priest]
    for offset in (0, 2):   # one opens on Quick Slash, the other on Power Dance
        f = Enemy("Kin Follower", CONTENT_RNG.randint(58, 59), list(follower_cycle),
                   _make_follower_choose(offset), category="boss")
        f.is_minion = True
        f.leader = priest
        units.append(f)
    return units


# --- Underdocks: the last of the normals -----------------------------------
# Three of these had been deferred for "undocumented statuses" (Ravenous,
# Suck, Surprise/Thievery). Reading the raw Underdocks data module shows
# those statuses appear NOWHERE in the enemies' actual movesets -- Corpse
# Slug, Fossil Stalker and Gremlin Merc are plain attackers, and the Merc's
# only special behavior is summoning on death. The earlier deferral came
# from a worse source, not from the data.

def _multi_hit(dmg, hits, extra=None):
    """N hits of the same damage, stopping early if the target dies, with an
    optional rider (apply Weak, gain Strength...) after the last hit."""
    def _resolve(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(hits):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(dmg), log=engine.log,
                                label=enemy.name, attacker=enemy)
        if extra is not None:
            extra(engine, enemy, target)
    return _resolve


def make_corpse_slug() -> Enemy:
    """Wiki: HP 25-27. Whip Slap (3 dmg x2); Glomp (8 dmg); Goop (2 Frail)."""
    whip_slap = Move("Whip Slap", IntentType.ATTACK, _multi_hit(3, 2), damage=3)
    glomp = Move("Glomp", IntentType.ATTACK, _dmg_move(8), damage=8)

    def _goop(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.add_status(StatusType.FRAIL, 2, applier=enemy)
        engine.log.append(f"{target.name} gains 2 Frail ({enemy.name})")
    goop = Move("Goop", IntentType.DEBUFF, _goop, damage=0)
    cycle = [whip_slap, glomp, goop]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    e = Enemy("Corpse Slug", CONTENT_RNG.randint(25, 27), cycle, choose)
    # Ravenous, from the enemy-powers module: "when an enemy dies, Corpse
    # Slug immediately eats it, becoming Stunned and gaining 2 Strength."
    e.add_status(StatusType.RAVENOUS, 2)
    return e


def make_fossil_stalker() -> Enemy:
    """Wiki: HP 51-53. Latch (12 dmg); Tackle (9 dmg, 1 Frail);
    Lash (3 dmg x2)."""
    latch = Move("Latch", IntentType.ATTACK, _dmg_move(12), damage=12)

    def _frail_rider(engine, enemy, target):
        target.add_status(StatusType.FRAIL, 1, applier=enemy)
    tackle = Move("Tackle", IntentType.ATTACK, _multi_hit(9, 1, _frail_rider), damage=9)
    lash = Move("Lash", IntentType.ATTACK, _multi_hit(3, 2), damage=3)
    cycle = [latch, tackle, lash]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    e = Enemy("Fossil Stalker", CONTENT_RNG.randint(51, 53), cycle, choose)
    # Suck: "whenever it deals unblocked attack damage, it gains 2 Strength."
    e.add_status(StatusType.SUCK, 2)
    return e


def make_fat_gremlin() -> Enemy:
    """Wiki: Minion, HP 13-17. Spawned (wakes up, does nothing); Flee
    (flees from combat with any stolen gold). With no gold system, Flee is
    modeled as simply leaving the fight -- it stops being a target and
    stops counting toward victory, which is the observable part."""
    spawned = Move("Spawned", IntentType.BUFF, _nothing, damage=0)

    def _flee(engine, enemy):
        enemy.alive = False
        enemy.death_resolved = True
        engine.log.append(f"{enemy.name} flees from combat")
    flee = Move("Flee", IntentType.BUFF, _flee, damage=0)

    def choose(enemy: Enemy, turn: int) -> Move:
        return spawned if turn == 0 else flee

    e = Enemy("Fat Gremlin", CONTENT_RNG.randint(13, 17), [spawned, flee], choose)
    e.is_minion = True
    return e


def make_sneaky_gremlin() -> Enemy:
    """Wiki: Minion, HP 10-14. Spawned (does nothing); Tackle (9 dmg)."""
    spawned = Move("Spawned", IntentType.BUFF, _nothing, damage=0)
    tackle = Move("Tackle", IntentType.ATTACK, _dmg_move(9), damage=9)

    def choose(enemy: Enemy, turn: int) -> Move:
        return spawned if turn == 0 else tackle

    e = Enemy("Sneaky Gremlin", CONTENT_RNG.randint(10, 14), [spawned, tackle], choose)
    e.is_minion = True
    return e


def make_gremlin_merc() -> Enemy:
    """Wiki: HP 47-49. Gimme (7 dmg x2); Double Smash (6 dmg x2, 2 Weak);
    Hehe (8 dmg, gains 2 Strength). Summons a Fat Gremlin and a Sneaky
    Gremlin ON DEATH -- so killing it does not end the encounter."""
    gimme = Move("Gimme", IntentType.ATTACK, _multi_hit(7, 2), damage=7)

    def _weak_rider(engine, enemy, target):
        target.add_status(StatusType.WEAK, 2, applier=enemy)
    double_smash = Move("Double Smash", IntentType.ATTACK,
                         _multi_hit(6, 2, _weak_rider), damage=6)

    def _str_rider(engine, enemy, target):
        enemy.add_status(StatusType.STRENGTH, 2)
    hehe = Move("Hehe", IntentType.ATTACK, _multi_hit(8, 1, _str_rider), damage=8)
    cycle = [gimme, double_smash, hehe]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    def _on_death(engine, enemy):
        engine.summon_enemy([make_fat_gremlin(), make_sneaky_gremlin()],
                             summoner=enemy, stunned=True)

    e = Enemy("Gremlin Merc", CONTENT_RNG.randint(47, 49), cycle, choose)
    e.on_death = _on_death
    return e


def make_gas_bomb() -> Enemy:
    """Wiki: Minion, HP 7. Explode (8 dmg, then dies). Summoned by Living
    Fog's Bloat."""
    def _explode(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(8), log=engine.log,
                            label=enemy.name, attacker=enemy)
        enemy.alive = False
        enemy.death_resolved = True
        engine.log.append(f"{enemy.name} explodes and dies")
    explode = Move("Explode", IntentType.ATTACK, _explode, damage=8)
    e = Enemy("Gas Bomb", 7, [explode], lambda en, t: explode)
    e.is_minion = True
    return e


def make_living_fog() -> Enemy:
    """Wiki: HP 80. Advanced Gas first (8 dmg, 1 Smoggy), then alternates
    Bloat (5 dmg, summons 1 Gas Bomb) and Super Gas Blast (8 dmg).

    Smoggy ("You can only play 1 Skill per turn") is NOT on the wiki's
    Buffs page -- its text comes from this enemy's own page, the same
    third-party-ish sourcing already used for Slippery and Skittish."""
    def _advanced_gas(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(8), log=engine.log,
                            label=enemy.name, attacker=enemy)
        target.add_status(StatusType.SMOGGY, 1, applier=enemy)
        engine.log.append(f"{target.name} gains 1 Smoggy (1 Skill per turn)")
    advanced_gas = Move("Advanced Gas", IntentType.DEBUFF, _advanced_gas, damage=8)

    def _bloat(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(5), log=engine.log,
                            label=enemy.name, attacker=enemy)
        engine.summon_enemy(make_gas_bomb(), summoner=enemy)
    bloat = Move("Bloat", IntentType.ATTACK, _bloat, damage=5)
    super_gas = Move("Super Gas Blast", IntentType.ATTACK, _dmg_move(8), damage=8)

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return advanced_gas
        return bloat if turn % 2 == 1 else super_gas

    return Enemy("Living Fog", 80, [advanced_gas, bloat, super_gas], choose)


def make_two_tailed_rat() -> Enemy:
    """Wiki: HP 17-21. Scratch (8 dmg); Disease Bite (6 dmg); Screech
    (1 Frail); Call for Backup (summons another Two-Tailed Rat).

    Call for Backup is unbounded in its own text -- the summoned rat can
    call for backup too -- so this relies on CombatEngine.MAX_ENEMIES to
    terminate. See that method's docstring."""
    scratch = Move("Scratch", IntentType.ATTACK, _dmg_move(8), damage=8)
    disease_bite = Move("Disease Bite", IntentType.ATTACK, _dmg_move(6), damage=6)

    def _screech(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.add_status(StatusType.FRAIL, 1, applier=enemy)
    screech = Move("Screech", IntentType.DEBUFF, _screech, damage=0)

    def _call_for_backup(engine, enemy):
        engine.summon_enemy(make_two_tailed_rat(), summoner=enemy, stunned=True)
    backup = Move("Call for Backup", IntentType.BUFF, _call_for_backup, damage=0)
    cycle = [scratch, backup, disease_bite, screech]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    return Enemy("Two-Tailed Rat", CONTENT_RNG.randint(17, 21),
                  [scratch, disease_bite, screech, backup], choose)


# --- Underdocks elites -----------------------------------------------------

def make_skulking_colony() -> Enemy:
    """Wiki: Elite, HP 75. Zoom (14 dmg); Inertia (9 dmg, gains 2 Strength);
    Piercing Stabs (7 dmg x2)."""
    zoom = Move("Zoom", IntentType.ATTACK, _dmg_move(14), damage=14)

    def _str_rider(engine, enemy, target):
        enemy.add_status(StatusType.STRENGTH, 2)
    inertia = Move("Inertia", IntentType.ATTACK, _multi_hit(9, 1, _str_rider), damage=9)
    stabs = Move("Piercing Stabs", IntentType.ATTACK, _multi_hit(7, 2), damage=7)
    cycle = [zoom, inertia, stabs]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    return Enemy("Skulking Colony", 75, cycle, choose, category="elite")


def make_terror_eel() -> Enemy:
    """Wiki: Elite, HP 140. Crash (16 dmg); Thrash (3 dmg x3, gains 6
    Vigor); Stun (does nothing); Terror (applies 99 Vulnerable).

    Terror's 99 Vulnerable is not a typo -- it is effectively permanent
    Vulnerable for the rest of the fight, which is what makes a 140 HP
    elite dangerous rather than just chunky."""
    crash = Move("Crash", IntentType.ATTACK, _dmg_move(16), damage=16)

    def _vigor_rider(engine, enemy, target):
        enemy.add_status(StatusType.VIGOR, 6)
        engine.log.append(f"{enemy.name} gains 6 Vigor")
    thrash = Move("Thrash", IntentType.ATTACK, _multi_hit(3, 3, _vigor_rider), damage=3)
    stun = Move("Stun", IntentType.BUFF, _nothing, damage=0)

    def _terror(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.VULNERABLE, 99, applier=enemy)
        engine.log.append(f"{enemy.name} applies 99 Vulnerable")
    terror = Move("Terror", IntentType.DEBUFF, _terror, damage=0)
    cycle = [terror, crash, thrash, stun]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    return Enemy("Terror Eel", 140, cycle, choose, category="elite")


# --- Underdocks bosses -----------------------------------------------------

def make_lagavulin_matriarch() -> Enemy:
    """Wiki: Boss, HP 222. Sleep (does nothing); Slash (19 dmg); Disembowel
    (9 dmg x2); Slash2 (12 dmg, gains 12 Block); Soul Siphon (removes 2
    Strength and 2 Dexterity from the player, gains 2 Strength).

    Soul Siphon is why STRENGTH_LOSS/DEXTERITY_LOSS exist as permanent
    positive counters: add_status() pops any status at <=0, so a player
    sitting at 0 Strength could not be pushed negative by a plain
    add_status(STRENGTH, -2)."""
    sleep = Move("Sleep", IntentType.BUFF, _nothing, damage=0)
    slash = Move("Slash", IntentType.ATTACK, _dmg_move(19), damage=19)
    disembowel = Move("Disembowel", IntentType.ATTACK, _multi_hit(9, 2), damage=9)

    def _block_rider(engine, enemy, target):
        enemy.gain_block(12)
    slash2 = Move("Guarded Slash", IntentType.ATTACK, _multi_hit(12, 1, _block_rider), damage=12)

    def _soul_siphon(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.STRENGTH_LOSS, 2, applier=enemy)
            p.add_status(StatusType.DEXTERITY_LOSS, 2, applier=enemy)
        enemy.add_status(StatusType.STRENGTH, 2)
        engine.log.append(f"{enemy.name} siphons 2 Strength and 2 Dexterity")
    soul_siphon = Move("Soul Siphon", IntentType.DEBUFF, _soul_siphon, damage=0)
    cycle = [slash, disembowel, slash2, soul_siphon]

    def choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return sleep
        return cycle[(turn - 1) % len(cycle)]

    return Enemy("Lagavulin Matriarch", 222,
                  [sleep] + cycle, choose, category="boss")


def make_soul_fysh() -> Enemy:
    """Wiki: Boss, HP 211. Fixed cycle: Beckon (shuffles 2 Beckon, 1 into
    the draw pile and 1 into the discard) / De-Gas (16 dmg) / Gaze (7 dmg,
    shuffles 1 Beckon into discard) / Fade (gains 2 Intangible) / Scream
    (13 dmg, applies 3 Vulnerable).

    Fade's Intangible is gained during the boss's own turn and Intangible
    is Duration/Decremented, so one stack expires at that turn's end and
    only one is left protecting it during the player's turn -- which
    matches the "first iteration fades instantly" quirk the wiki notes,
    and falls out of the existing status rules rather than being special-
    cased."""
    def _beckon(engine, enemy):
        target = engine.pick_enemy_attack_target()
        card = make_beckon()
        target.draw_pile.insert(0, card)
        target.discard_pile.append(make_beckon())
        engine.log.append(f"{target.name} gets 2 Beckon (1 draw pile, 1 discard)")
    beckon = Move("Beckon", IntentType.DEBUFF, _beckon, damage=0)
    de_gas = Move("De-Gas", IntentType.ATTACK, _dmg_move(16), damage=16)

    def _gaze_rider(engine, enemy, target):
        _shuffle_status_cards(engine, target, make_beckon, 1, "Beckon")
    gaze = Move("Gaze", IntentType.ATTACK, _multi_hit(7, 1, _gaze_rider), damage=7)

    def _fade(engine, enemy):
        enemy.add_status(StatusType.INTANGIBLE, 2)
        engine.log.append(f"{enemy.name} gains 2 Intangible")
    fade = Move("Fade", IntentType.BUFF, _fade, damage=0)

    def _scream_rider(engine, enemy, target):
        target.add_status(StatusType.VULNERABLE, 3, applier=enemy)
    scream = Move("Scream", IntentType.ATTACK, _multi_hit(13, 1, _scream_rider), damage=13)
    cycle = [beckon, de_gas, gaze, fade, scream]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    return Enemy("Soul Fysh", 211, cycle, choose, category="boss")


def make_waterfall_giant() -> Enemy:
    """Wiki: Boss, HP 240. Every move feeds a Steam Eruption counter:
    Pressurize (+15); Stomp (15 dmg, 1 Weak, +3); Ram (10 dmg, +3); Siphon
    (heals 15 HP PER PLAYER, +3); Pressure Gun (20 dmg, +5 more each use,
    +3); Pressure Up (13 dmg, +3).

    CORRECTED: Steam Eruption is "when killed, deals X damage at the end of
    your next turn" -- a posthumous bomb, not a self-destruct timer. The
    first port had it as a charge the boss spent on its own About To Blow ->
    Explode finale, which made it suicide on turn 8 and benchmark at 37%
    while every other Act 1 boss sat at 0%. That was an invented move order,
    and the number was an artifact of it.

    The two moves whose trigger is still unknown (About To Blow, Explode)
    are therefore NOT in the cycle: the death trigger is what the documented
    power actually does. See task #38."""
    def _steam(enemy, amount=3):
        enemy.add_status(StatusType.STEAM_ERUPTION, amount)

    def _pressurize(engine, enemy):
        _steam(enemy, 15)
        engine.log.append(f"{enemy.name} gains 15 Steam Eruption")
    pressurize = Move("Pressurize", IntentType.BUFF, _pressurize, damage=0)

    def _stomp(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(15), log=engine.log,
                            label=enemy.name, attacker=enemy)
        target.add_status(StatusType.WEAK, 1, applier=enemy)
        _steam(enemy)
    stomp = Move("Stomp", IntentType.ATTACK, _stomp, damage=15)

    def _ram(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(10), log=engine.log,
                            label=enemy.name, attacker=enemy)
        _steam(enemy)
    ram = Move("Ram", IntentType.ATTACK, _ram, damage=10)

    def _siphon(engine, enemy):
        healed = 15 * len(engine.players)
        enemy.heal(healed)
        _steam(enemy)
        engine.log.append(f"{enemy.name} heals {healed} HP (15 per player)")
    siphon = Move("Siphon", IntentType.BUFF, _siphon, damage=0)

    def _pressure_gun(engine, enemy):
        dmg = 20 + 5 * getattr(enemy, "pressure_gun_uses", 0)
        enemy.pressure_gun_uses = getattr(enemy, "pressure_gun_uses", 0) + 1
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(dmg), log=engine.log,
                            label=enemy.name, attacker=enemy)
        _steam(enemy)
    pressure_gun = Move("Pressure Gun", IntentType.ATTACK, _pressure_gun, damage=20)

    def _pressure_up(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(13), log=engine.log,
                            label=enemy.name, attacker=enemy)
        _steam(enemy)
    pressure_up = Move("Pressure Up", IntentType.ATTACK, _pressure_up, damage=13)

    cycle = [pressurize, stomp, ram, pressure_gun, siphon, pressure_up]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    return Enemy("Waterfall Giant", 240, cycle, choose, category="boss")


# ===========================================================================
# EVENT-ONLY ENEMIES -- Module:Enemies/StS2_data/Events, the SEVENTH enemy
# data module. It is referenced by the main aggregator module but not by any
# region page, so a region-by-region sweep misses it entirely; found only by
# reading the aggregator's own list of submodules.
# ===========================================================================

def make_the_merchant() -> Enemy:
    """Wiki: Event enemy, HP 165, from a Hive/Glory event encounter.
    Swipe (13 dmg); Spew Coins (2 dmg x8); Throw Relic (9 dmg, 1 Frail);
    Enrage (gains 2 Strength)."""
    swipe = Move("Swipe", IntentType.ATTACK, _dmg_move(13), damage=13)
    spew = Move("Spew Coins", IntentType.ATTACK, _multi_hit(2, 8), damage=2)

    def _frail_rider(engine, enemy, target):
        target.add_status(StatusType.FRAIL, 1, applier=enemy)
    throw_relic = Move("Throw Relic", IntentType.ATTACK,
                        _multi_hit(9, 1, _frail_rider), damage=9)

    def _enrage(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    enrage = Move("Enrage", IntentType.BUFF, _enrage, damage=0)
    cycle = [swipe, spew, throw_relic, enrage]
    return Enemy("The Merchant???", 165, cycle, lambda e, t: cycle[t % 4])


def _make_battle_friend(version: int, hp: int) -> Enemy:
    """Glory event encounter. Its only intent is literally "Nothing -- does
    nothing", so this is a pure punching bag whose whole content is its HP
    pool. Ported because it is in the data module, not because it is
    interesting."""
    nothing = Move("Nothing", IntentType.BUFF, _nothing, damage=0)
    return Enemy(f"Battle Friend V{version}.0", hp, [nothing], lambda e, t: nothing)


def make_battle_friend_v1() -> Enemy:
    return _make_battle_friend(1, 75)


def make_battle_friend_v2() -> Enemy:
    return _make_battle_friend(2, 150)


def make_battle_friend_v3() -> Enemy:
    return _make_battle_friend(3, 300)


# ===========================================================================
# ACT 2 -- THE HIVE. A single region (unlike Act 1's two), themed on a bug
# nest. Numbers from Module:Enemies/StS2_data/Hive plus the Elites/Bosses
# modules. Move ORDER is published for only a few of these; the rest use a
# fixed loop, same caveat as Act 1.
#
# Use act="act2" when constructing the engine so multiplayer HP/Block
# scaling picks up the 1.2 act multiplier.
# ===========================================================================

def _bowlbug(name, hp_range, moves, choose):
    return Enemy(name, CONTENT_RNG.randint(*hp_range), moves, choose)


def make_bowlbug_rock() -> Enemy:
    """Wiki: HP 45-48. Headbutt (15 dmg); Dizzy (stunned, does nothing).
    Alternates -- it knocks itself silly on the follow-through."""
    headbutt = Move("Headbutt", IntentType.ATTACK, _dmg_move(15), damage=15)
    dizzy = Move("Dizzy", IntentType.BUFF, _nothing, damage=0)
    cycle = [headbutt, dizzy]
    return _bowlbug("Bowlbug (Rock)", (45, 48), cycle,
                     lambda e, t: cycle[t % 2])


def make_bowlbug_egg() -> Enemy:
    """Wiki: HP 21-22. Bite (7 dmg, gains 7 Block) -- its only move."""
    def _bite(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(7), log=engine.log,
                            label=enemy.name, attacker=enemy)
        enemy.gain_block(7)
    bite = Move("Bite", IntentType.ATTACK, _bite, damage=7)
    return _bowlbug("Bowlbug (Egg)", (21, 22), [bite], lambda e, t: bite)


def make_bowlbug_silk() -> Enemy:
    """Wiki: HP 40-43. Thrash (4 dmg x2); Spin Web (applies 1 Weak)."""
    thrash = Move("Thrash", IntentType.ATTACK, _multi_hit(4, 2), damage=4)

    def _spin_web(engine, enemy):
        engine.pick_enemy_attack_target().add_status(StatusType.WEAK, 1, applier=enemy)
    spin_web = Move("Spin Web", IntentType.DEBUFF, _spin_web, damage=0)
    cycle = [thrash, spin_web]
    return _bowlbug("Bowlbug (Silk)", (40, 43), cycle, lambda e, t: cycle[t % 2])


def make_bowlbug_nectar() -> Enemy:
    """Wiki: HP 35-38. Thrash (3 dmg); Buff (gains 15 Strength).

    That 15 Strength is not a typo -- it is a low-damage bug that turns
    terrifying if left alive, which is the point of the encounter."""
    thrash = Move("Thrash", IntentType.ATTACK, _dmg_move(3), damage=3)

    def _buff(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 15)
        engine.log.append(f"{enemy.name} gains 15 Strength")
    buff = Move("Buff", IntentType.BUFF, _buff, damage=0)
    cycle = [thrash, buff]
    return _bowlbug("Bowlbug (Nectar)", (35, 38), cycle, lambda e, t: cycle[t % 2])


def make_chomper() -> Enemy:
    """Wiki: HP 60-64. Clamp (8 dmg x2); Screech (shuffles 3 Dazed)."""
    clamp = Move("Clamp", IntentType.ATTACK, _multi_hit(8, 2), damage=8)

    def _screech(engine, enemy):
        _shuffle_status_cards(engine, engine.pick_enemy_attack_target(),
                               make_dazed, 3, "Dazed")
    screech = Move("Screech", IntentType.DEBUFF, _screech, damage=0)
    cycle = [clamp, screech]
    return Enemy("Chomper", CONTENT_RNG.randint(60, 64), cycle, lambda e, t: cycle[t % 2])


def make_exoskeleton() -> Enemy:
    """Wiki: HP 24-28. Skitter (1 dmg x3); Mandibles (8 dmg); Enrage
    (gains 2 Strength)."""
    skitter = Move("Skitter", IntentType.ATTACK, _multi_hit(1, 3), damage=1)
    mandibles = Move("Mandibles", IntentType.ATTACK, _dmg_move(8), damage=8)

    def _enrage(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    enrage = Move("Enrage", IntentType.BUFF, _enrage, damage=0)
    cycle = [skitter, mandibles, enrage]
    return Enemy("Exoskeleton", CONTENT_RNG.randint(24, 28), cycle,
                  lambda e, t: cycle[t % 3])


def make_hunter_killer() -> Enemy:
    """Wiki: HP 121. Opens with Tenderizing Goop (applies 1 Tender), then
    alternates Bite (17) and Puncture (7 x3).

    Tender -- "whenever you play a card, lose X Strength and X Dexterity
    this turn" -- is not on the wiki's Buffs page; the text comes from this
    enemy's own page. It punishes wide turns specifically, which is a
    different pressure from anything in Act 1."""
    def _goop(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.TENDER, 1, applier=enemy)
        engine.log.append(f"{enemy.name} applies 1 Tender")
    goop = Move("Tenderizing Goop", IntentType.DEBUFF, _goop, damage=0)
    bite = Move("Bite", IntentType.ATTACK, _dmg_move(17), damage=17)
    puncture = Move("Puncture", IntentType.ATTACK, _multi_hit(7, 3), damage=7)
    # The wiki says Puncture is twice as likely as Bite and Bite never
    # repeats; a fixed loop reproduces both properties without needing rng.
    after = [puncture, bite, puncture]

    def choose(enemy: Enemy, turn: int) -> Move:
        return goop if turn == 0 else after[(turn - 1) % len(after)]

    return Enemy("Hunter Killer", 121, [goop, bite, puncture], choose)


def make_louse_progenitor() -> Enemy:
    """Wiki: HP 134-136. Web Cannon (9 dmg, 2 Frail); Curl and Grow (gains
    14 Block and 5 Strength); Pounce (14 dmg)."""
    def _web_rider(engine, enemy, target):
        target.add_status(StatusType.FRAIL, 2, applier=enemy)
    web_cannon = Move("Web Cannon", IntentType.ATTACK, _multi_hit(9, 1, _web_rider), damage=9)

    def _curl(engine, enemy):
        enemy.gain_block(14)
        enemy.add_status(StatusType.STRENGTH, 5)
    curl = Move("Curl and Grow", IntentType.DEFEND, _curl, damage=0)
    pounce = Move("Pounce", IntentType.ATTACK, _dmg_move(14), damage=14)
    cycle = [web_cannon, curl, pounce]
    return Enemy("Louse Progenitor", CONTENT_RNG.randint(134, 136), cycle,
                  lambda e, t: cycle[t % 3])


def make_mysterious_knight() -> Enemy:
    """Wiki: HP 101. Breaker (gains 3 Strength); Flail (9 dmg x2);
    Ram (15 dmg)."""
    def _breaker(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 3)
    breaker = Move("Breaker", IntentType.BUFF, _breaker, damage=0)
    flail = Move("Flail", IntentType.ATTACK, _multi_hit(9, 2), damage=9)
    ram = Move("Ram", IntentType.ATTACK, _dmg_move(15), damage=15)
    cycle = [breaker, flail, ram]
    return Enemy("Mysterious Knight", 101, cycle, lambda e, t: cycle[t % 3])


def make_myte() -> Enemy:
    """Wiki: HP 61-67. Toxic Cornucopia (adds 2 Toxic to your HAND -- note
    hand, not discard pile, so they bite the same turn); Bite (13 dmg);
    Suck (4 dmg, gains 2 Strength)."""
    def _cornucopia(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(2):
            target.add_to_hand(make_toxic(), engine.log)
        engine.log.append(f"{target.name} gains 2 Toxic in hand ({enemy.name})")
    cornucopia = Move("Toxic Cornucopia", IntentType.DEBUFF, _cornucopia, damage=0)
    bite = Move("Bite", IntentType.ATTACK, _dmg_move(13), damage=13)

    def _suck_rider(engine, enemy, target):
        enemy.add_status(StatusType.STRENGTH, 2)
    suck = Move("Suck", IntentType.ATTACK, _multi_hit(4, 1, _suck_rider), damage=4)
    cycle = [cornucopia, bite, suck]
    return Enemy("Myte", CONTENT_RNG.randint(61, 67), cycle, lambda e, t: cycle[t % 3])


def make_hatchling() -> Enemy:
    """What a Tough Egg becomes. Wiki gives it 19-22 HP; its moveset is not
    published separately, so it reuses the Egg's Nibble at a size that fits
    its HP -- flagged as an approximation."""
    nibble = Move("Nibble", IntentType.ATTACK, _dmg_move(6), damage=6)
    e = Enemy("Hatchling", CONTENT_RNG.randint(19, 22), [nibble], lambda en, t: nibble)
    e.is_minion = True
    return e


def make_tough_egg() -> Enemy:
    """Wiki: Minion, HP 14-18. Hatch (becomes a Hatchling with 19-22 HP);
    Nibble (4 dmg). Summoned three at a time by Ovicopter.

    Hatching is modeled as the egg dying and a Hatchling being summoned in
    its place, which is the only shape this engine has for "one enemy turns
    into another" -- noted because it means AOE that kills the egg first
    prevents the hatch entirely."""
    def _hatch(engine, enemy):
        engine.summon_enemy(make_hatchling(), summoner=enemy)
        enemy.alive = False
        enemy.death_resolved = True
        engine.log.append(f"{enemy.name} hatches")
    hatch = Move("Hatch", IntentType.BUFF, _hatch, damage=0)
    nibble = Move("Nibble", IntentType.ATTACK, _dmg_move(4), damage=4)

    def choose(enemy: Enemy, turn: int) -> Move:
        return nibble if turn == 0 else hatch

    e = Enemy("Tough Egg", CONTENT_RNG.randint(14, 18), [nibble, hatch], choose)
    e.is_minion = True
    return e


def make_ovicopter() -> Enemy:
    """Wiki: HP 124-130. Lay Eggs (summons 3 Tough Eggs); Smash (16 dmg);
    Tenderizer (7 dmg, 2 Vulnerable); Nutritional Paste (gains 3 Strength)."""
    def _lay_eggs(engine, enemy):
        engine.summon_enemy([make_tough_egg() for _ in range(3)], summoner=enemy)
    lay_eggs = Move("Lay Eggs", IntentType.BUFF, _lay_eggs, damage=0)
    smash = Move("Smash", IntentType.ATTACK, _dmg_move(16), damage=16)

    def _vuln_rider(engine, enemy, target):
        target.add_status(StatusType.VULNERABLE, 2, applier=enemy)
    tenderizer = Move("Tenderizer", IntentType.ATTACK, _multi_hit(7, 1, _vuln_rider), damage=7)

    def _paste(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 3)
    paste = Move("Nutritional Paste", IntentType.BUFF, _paste, damage=0)
    cycle = [lay_eggs, tenderizer, smash, paste]
    return Enemy("Ovicopter", CONTENT_RNG.randint(124, 130), cycle,
                  lambda e, t: cycle[t % 4])


def make_slumbering_beetle() -> Enemy:
    """Wiki: HP 86. Snore (asleep, does nothing); Roll Out (16 dmg, gains 2
    Strength). Opens asleep."""
    snore = Move("Snore", IntentType.BUFF, _nothing, damage=0)

    def _roll_rider(engine, enemy, target):
        enemy.add_status(StatusType.STRENGTH, 2)
    roll_out = Move("Roll Out", IntentType.ATTACK, _multi_hit(16, 1, _roll_rider), damage=16)

    def choose(enemy: Enemy, turn: int) -> Move:
        return snore if turn == 0 else roll_out

    return Enemy("Slumbering Beetle", 86, [snore, roll_out], choose)


def make_spiny_toad() -> Enemy:
    """Wiki: HP 116-119. Protruding Spikes (gains 5 Thorns); Spike Explosion
    (23 dmg, loses 5 Thorns); Tongue Lash (17 dmg).

    Act 1's Toadpole with the numbers turned up -- same gain-then-spend
    Thorns rhythm, which is why Thorns had to fire per hit."""
    def _spikes(engine, enemy):
        enemy.add_status(StatusType.THORNS, 5)
        engine.log.append(f"{enemy.name} gains 5 Thorns")
    spikes = Move("Protruding Spikes", IntentType.BUFF, _spikes, damage=0)

    def _explosion(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(23), log=engine.log,
                            label=enemy.name, attacker=enemy)
        enemy.add_status(StatusType.THORNS, -5)
    explosion = Move("Spike Explosion", IntentType.ATTACK, _explosion, damage=23)
    tongue = Move("Tongue Lash", IntentType.ATTACK, _dmg_move(17), damage=17)
    cycle = [spikes, tongue, explosion]
    return Enemy("Spiny Toad", CONTENT_RNG.randint(116, 119), cycle,
                  lambda e, t: cycle[t % 3])


def make_parafright() -> Enemy:
    """Wiki: Minion, HP 21. Slam (16 dmg). Summoned by The Obscura."""
    slam = Move("Slam", IntentType.ATTACK, _dmg_move(16), damage=16)
    e = Enemy("Parafright", 21, [slam], lambda en, t: slam)
    e.is_minion = True
    return e


def make_the_obscura() -> Enemy:
    """Wiki: HP 123. Illusion (summons a Parafright); Piercing Gaze (10 dmg);
    Wail (ALL enemies gain 3 Strength); Hardening Strike (6 dmg, gains 6
    Block).

    Wail buffing every enemy makes this the first porting case where an
    enemy move targets its own side as a group."""
    def _illusion(engine, enemy):
        engine.summon_enemy(make_parafright(), summoner=enemy)
    illusion = Move("Illusion", IntentType.BUFF, _illusion, damage=0)
    gaze = Move("Piercing Gaze", IntentType.ATTACK, _dmg_move(10), damage=10)

    def _wail(engine, enemy):
        for e in engine.enemies_alive():
            e.add_status(StatusType.STRENGTH, 3)
        engine.log.append(f"{enemy.name} wails: ALL enemies gain 3 Strength")
    wail = Move("Wail", IntentType.BUFF, _wail, damage=0)

    def _harden_rider(engine, enemy, target):
        enemy.gain_block(6)
    hardening = Move("Hardening Strike", IntentType.ATTACK,
                      _multi_hit(6, 1, _harden_rider), damage=6)
    cycle = [illusion, gaze, wail, hardening]
    return Enemy("The Obscura", 123, cycle, lambda e, t: cycle[t % 4])


def make_thieving_hopper() -> Enemy:
    """Wiki: HP 79. Thievery (17 dmg, steals a card from your deck); Flutter
    (gains Flutter: takes 50% less Attack damage, must be hit 5 times);
    Hat Trick (21 dmg); Nab (14 dmg); Escape (flees with any stolen cards).

    Stolen cards are pulled out of the draw pile and held by the enemy. If
    it escapes with them they are gone for the rest of the fight; kill it
    first and they come back. With no run/deck persistence layer yet (#31),
    the theft is combat-scoped -- flagged, since in the real game losing a
    card matters beyond the fight."""
    def _thievery(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(17), log=engine.log,
                            label=enemy.name, attacker=enemy)
        if target.draw_pile:
            stolen = target.draw_pile.pop()
            enemy.stolen_cards.append((target, stolen))
            engine.log.append(f"{enemy.name} steals {stolen.name}")
    thievery = Move("Thievery", IntentType.ATTACK, _thievery, damage=17)

    def _flutter(engine, enemy):
        enemy.add_status(StatusType.FLUTTER, 5)
        engine.log.append(f"{enemy.name} gains Flutter (50% less attack damage, 5 hits)")
    flutter = Move("Flutter", IntentType.DEFEND, _flutter, damage=0)
    hat_trick = Move("Hat Trick", IntentType.ATTACK, _dmg_move(21), damage=21)
    nab = Move("Nab", IntentType.ATTACK, _dmg_move(14), damage=14)

    def _escape(engine, enemy):
        enemy.alive = False
        enemy.death_resolved = True
        engine.log.append(
            f"{enemy.name} escapes with {len(enemy.stolen_cards)} stolen card(s)")
    escape = Move("Escape", IntentType.BUFF, _escape, damage=0)
    cycle = [thievery, flutter, nab, hat_trick, escape]

    def choose(enemy: Enemy, turn: int) -> Move:
        return cycle[turn % len(cycle)]

    def _on_death(engine, enemy):
        # Killed before it escapes -> the cards come back.
        for owner, card in enemy.stolen_cards:
            owner.discard_pile.append(card)
        if enemy.stolen_cards:
            engine.log.append(f"{len(enemy.stolen_cards)} stolen card(s) recovered")
        enemy.stolen_cards = []

    e = Enemy("Thieving Hopper", 79, cycle, choose)
    e.stolen_cards = []
    e.on_death = _on_death
    return e


def make_tunneler() -> Enemy:
    """Wiki: HP 87. Bite (13 dmg) -> Burrow (gains Burrowed and 32 Block) ->
    Attack from Below (23 dmg) every turn while burrowed -> once its Block
    is fully broken, Emerging Strike (stunned, does nothing) -> repeat.

    Burrowed means its Block is NOT cleared at the start of its turn, so
    that 32 Block persists until you chew through it. The "block fully
    broken" trigger is checked when it picks its next move."""
    bite = Move("Bite", IntentType.ATTACK, _dmg_move(13), damage=13)

    def _burrow(engine, enemy):
        enemy.add_status(StatusType.BURROWED, 1)
        enemy.gain_block(32)
        engine.log.append(f"{enemy.name} burrows and gains 32 Block")
    burrow = Move("Burrow", IntentType.DEFEND, _burrow, damage=0)
    below = Move("Attack from Below", IntentType.ATTACK, _dmg_move(23), damage=23)

    def _emerge(engine, enemy):
        enemy.statuses.pop(StatusType.BURROWED, None)
        engine.log.append(f"{enemy.name} is forced out of the ground")
    emerging = Move("Emerging Strike", IntentType.BUFF, _emerge, damage=0)

    def choose(enemy: Enemy, turn: int) -> Move:
        if enemy.has_status(StatusType.BURROWED):
            return emerging if enemy.block <= 0 else below
        return bite if turn == 0 or getattr(enemy, "just_emerged", False) else burrow

    return Enemy("Tunneler", 87, [bite, burrow, below, emerging], choose)


# --- Hive elites -----------------------------------------------------------

def make_decimillipede_group() -> List[Enemy]:
    """Wiki: Elite, THREE segments of 40-46 HP each, staggered across the
    same 3-move cycle: Bulk (6 dmg, gains 2 Strength) / Writhe (5 dmg x2) /
    Outgas (8 dmg, applies 1 Weak).

    Reattach: a segment that dies revives with 25 HP as its next action, but
    ONLY if another segment is still alive -- so the fight ends when they
    all drop close enough together. Implemented as an on_death that resummons
    the segment; the revived one picks a random move, matching the wiki's
    note that reviving desynchronizes the group."""
    def _bulk_rider(engine, enemy, target):
        enemy.add_status(StatusType.STRENGTH, 2)
    bulk = Move("Bulk", IntentType.ATTACK, _multi_hit(6, 1, _bulk_rider), damage=6)
    writhe = Move("Writhe", IntentType.ATTACK, _multi_hit(5, 2), damage=5)

    def _weak_rider(engine, enemy, target):
        target.add_status(StatusType.WEAK, 1, applier=enemy)
    outgas = Move("Outgas", IntentType.ATTACK, _multi_hit(8, 1, _weak_rider), damage=8)
    cycle = [bulk, writhe, outgas]

    def _make_choose(offset):
        def choose(enemy: Enemy, turn: int) -> Move:
            if getattr(enemy, "reattached", False):
                enemy.reattached = False
                return enemy.rng.choice(cycle)
            return cycle[(turn + offset) % len(cycle)]
        return choose

    def _schedule_reattach(engine, enemy):
        """Powers module: "if other segments are still alive, revives in 2
        turns with X HP." The 2-turn delay matters -- it is the window where
        killing the rest of the segments actually finishes the fight."""
        others = [e for e in engine.enemies
                  if e.alive and e.name == "Decimillipede" and e is not enemy]
        if not others:
            return
        enemy.revive_in = 2
        engine.log.append(f"{enemy.name} will reattach in 2 turns")

    def _reattach(engine, enemy):
        others = [e for e in engine.enemies
                  if e.alive and e.name == "Decimillipede" and e is not enemy]
        if not others:
            return   # everything else died while it was waiting: stay dead
        enemy.alive = True
        enemy.hp = 25
        enemy.death_resolved = False
        enemy.reattached = True
        engine.log.append(f"{enemy.name} reattaches and revives with 25 HP")

    segments = []
    for offset in range(3):
        seg = Enemy("Decimillipede", CONTENT_RNG.randint(40, 46), list(cycle),
                     _make_choose(offset), category="elite")
        seg.on_death = _schedule_reattach
        seg.on_revive = _reattach
        segments.append(seg)
    return segments


def make_entomancer() -> Enemy:
    """Wiki: Elite, HP 145. Beeeees! (3 dmg x7); Spear! (18 dmg); Pheromone
    Spit (gains 1 Personal Hive and 1 Strength).

    Personal Hive ("whenever this enemy is hit by an Attack, add X Dazed
    into your Draw Pile") was undocumented on every page I first checked and
    was left unimplemented; it is defined in Module:Powers/StS2_data/Enemy,
    which is where all the enemy PASSIVE powers live -- separate from the
    movesets. Now implemented, so attacking it repeatedly clogs your deck."""
    beees = Move("Beeeees!", IntentType.ATTACK, _multi_hit(3, 7), damage=3)
    spear = Move("Spear!", IntentType.ATTACK, _dmg_move(18), damage=18)

    def _pheromone(engine, enemy):
        enemy.add_status(StatusType.PERSONAL_HIVE, 1)
        enemy.add_status(StatusType.STRENGTH, 1)
        engine.log.append(f"{enemy.name} gains 1 Personal Hive and 1 Strength")
    pheromone = Move("Pheromone Spit", IntentType.BUFF, _pheromone, damage=0)
    cycle = [pheromone, beees, spear]
    return Enemy("Entomancer", 145, cycle, lambda e, t: cycle[t % 3], category="elite")


def make_infested_prism() -> Enemy:
    """Wiki: Elite, HP 161. Jab (15 dmg); Radiate (11 dmg, gains 16 Block);
    Whirlwind (5 dmg x3); Pulsate (8 dmg, gains 20 Block).

    Pulsate's entry is truncated on the wiki after the Block clause, so only
    the documented half is implemented."""
    jab = Move("Jab", IntentType.ATTACK, _dmg_move(15), damage=15)

    def _block_rider(amount):
        def rider(engine, enemy, target):
            enemy.gain_block(amount)
        return rider
    radiate = Move("Radiate", IntentType.ATTACK, _multi_hit(11, 1, _block_rider(16)), damage=11)
    whirlwind = Move("Whirlwind", IntentType.ATTACK, _multi_hit(5, 3), damage=5)
    pulsate = Move("Pulsate", IntentType.ATTACK, _multi_hit(8, 1, _block_rider(20)), damage=8)
    cycle = [jab, radiate, whirlwind, pulsate]
    return Enemy("Infested Prism", 161, cycle, lambda e, t: cycle[t % 4], category="elite")


# --- Hive bosses -----------------------------------------------------------

def make_the_insatiable() -> Enemy:
    """Wiki: Boss, HP 321. Opens with Liquify Ground (gains 4 Sandpit per
    player and shuffles 6 Frantic Escape into each deck), then cycles
    Thrash (8 dmg x2) / Lunging Bite (28 dmg) / Salivate (gains 2 Strength).

    Sandpit is a countdown to death, not damage: "in X turns you will be
    eaten and die". Frantic Escape ("increase Sandpit by 1, increase the
    cost of this card by 1") is the way out -- the fight is a race between
    digging yourself out and the boss's damage."""
    def _liquify(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.SANDPIT, 4, applier=enemy)
            for _ in range(3):
                p.draw_pile.insert(0, make_frantic_escape())
                p.discard_pile.append(make_frantic_escape())
        engine.log.append(f"{enemy.name} liquifies the ground: 4 Sandpit and 6 Frantic Escape")
    liquify = Move("Liquify Ground", IntentType.DEBUFF, _liquify, damage=0)
    thrash = Move("Thrash", IntentType.ATTACK, _multi_hit(8, 2), damage=8)
    lunging = Move("Lunging Bite", IntentType.ATTACK, _dmg_move(28), damage=28)

    def _salivate(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    salivate = Move("Salivate", IntentType.BUFF, _salivate, damage=0)
    after = [thrash, lunging, salivate, thrash]

    def choose(enemy: Enemy, turn: int) -> Move:
        return liquify if turn == 0 else after[(turn - 1) % len(after)]

    return Enemy("The Insatiable", 321,
                  [liquify, thrash, lunging, salivate], choose, category="boss")


def make_knowledge_demon() -> Enemy:
    """Wiki: Boss, HP 379. Curse of Knowledge (each player chooses one of
    two debuffs); Slap (17 dmg); Knowledge Overwhelming (8 dmg x3); Ponder
    (11 dmg, heals 30 HP per player, gains 2 Strength).

    Curse of Knowledge is an interactive choice with no UI hook in this
    replica -- the same wall the Gambling Chip relic hit. It auto-picks
    Weak, which is the milder of the two typical options; flagged as an
    approximation rather than a verified rule."""
    def _curse(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.WEAK, 2, applier=enemy)
        engine.log.append(f"{enemy.name} forces a choice of debuff (auto-picked Weak)")
    curse = Move("Curse of Knowledge", IntentType.DEBUFF, _curse, damage=0)
    slap = Move("Slap", IntentType.ATTACK, _dmg_move(17), damage=17)
    overwhelming = Move("Knowledge Overwhelming", IntentType.ATTACK,
                         _multi_hit(8, 3), damage=8)

    def _ponder(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(11), log=engine.log,
                            label=enemy.name, attacker=enemy)
        healed = 30 * len(engine.players)
        enemy.heal(healed)
        enemy.add_status(StatusType.STRENGTH, 2)
        engine.log.append(f"{enemy.name} heals {healed} HP (30 per player)")
    ponder = Move("Ponder", IntentType.ATTACK, _ponder, damage=11)
    cycle = [curse, slap, overwhelming, ponder]
    return Enemy("Knowledge Demon", 379, cycle, lambda e, t: cycle[t % 4],
                  category="boss")


def make_kaiser_crab() -> List[Enemy]:
    """Wiki: the Kaiser Crab boss fight is TWO units -- Crusher (209 HP) and
    Rocket (199 HP) -- not one.

    Crusher: Thrash (12) / Enlarging Strike (4) / Bug Sting (6x2, 2 Weak and
    2 Frail) / Adapt (+2 Strength) / Guarded Strike (12, gains 18 Block).
    Rocket: Targeting Reticle (3) / Precision Beam (18) / Charge Up
    (+2 Strength) / Laser (31) / Recharge (nothing).

    No published move order for either, so both use a fixed loop."""
    thrash = Move("Thrash", IntentType.ATTACK, _dmg_move(12), damage=12)
    enlarging = Move("Enlarging Strike", IntentType.ATTACK, _dmg_move(4), damage=4)

    def _sting_rider(engine, enemy, target):
        target.add_status(StatusType.WEAK, 2, applier=enemy)
        target.add_status(StatusType.FRAIL, 2, applier=enemy)
    bug_sting = Move("Bug Sting", IntentType.ATTACK, _multi_hit(6, 2, _sting_rider), damage=6)

    def _adapt(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    adapt = Move("Adapt", IntentType.BUFF, _adapt, damage=0)

    def _guard_rider(engine, enemy, target):
        enemy.gain_block(18)
    guarded = Move("Guarded Strike", IntentType.ATTACK, _multi_hit(12, 1, _guard_rider), damage=12)
    crusher_cycle = [enlarging, adapt, bug_sting, thrash, guarded]
    crusher = Enemy("Crusher", 209, crusher_cycle,
                     lambda e, t: crusher_cycle[t % len(crusher_cycle)], category="boss")

    reticle = Move("Targeting Reticle", IntentType.ATTACK, _dmg_move(3), damage=3)
    beam = Move("Precision Beam", IntentType.ATTACK, _dmg_move(18), damage=18)

    def _charge(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    charge = Move("Charge Up", IntentType.BUFF, _charge, damage=0)
    laser = Move("Laser", IntentType.ATTACK, _dmg_move(31), damage=31)
    recharge = Move("Recharge", IntentType.BUFF, _nothing, damage=0)
    rocket_cycle = [reticle, charge, beam, laser, recharge]
    rocket = Enemy("Rocket", 199, rocket_cycle,
                    lambda e, t: rocket_cycle[t % len(rocket_cycle)], category="boss")
    return [crusher, rocket]


# ===========================================================================
# ACT 3 -- GLORY. One region, like the Hive. Numbers from
# Module:Enemies/StS2_data/Glory plus the Elites/Bosses modules.
#
# Use act="act3" (or "act3boss") when constructing the engine.
# ===========================================================================

def make_devoted_sculptor() -> Enemy:
    """Wiki: HP 162. Forbidden Incantation (gains 9 Ritual); Savage (12 dmg).
    9 Ritual is enormous -- it gains 9 Strength at the start of every one of
    its turns thereafter, so this is a hard timer."""
    def _incantation(engine, enemy):
        enemy.add_status(StatusType.RITUAL, 9)
        engine.log.append(f"{enemy.name} gains 9 Ritual")
    incantation = Move("Forbidden Incantation", IntentType.BUFF, _incantation, damage=0)
    savage = Move("Savage", IntentType.ATTACK, _dmg_move(12), damage=12)

    def choose(enemy: Enemy, turn: int) -> Move:
        return incantation if turn == 0 else savage

    return Enemy("Devoted Sculptor", 162, [incantation, savage], choose)


def make_scroll_of_biting() -> Enemy:
    """Wiki: HP 31-38. Chomp (14 dmg); More Teeth (gains 2 Strength);
    Chew (5 dmg x2)."""
    chomp = Move("Chomp", IntentType.ATTACK, _dmg_move(14), damage=14)

    def _more_teeth(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    more_teeth = Move("More Teeth", IntentType.BUFF, _more_teeth, damage=0)
    chew = Move("Chew", IntentType.ATTACK, _multi_hit(5, 2), damage=5)
    cycle = [chomp, more_teeth, chew]
    return Enemy("Scroll of Biting", CONTENT_RNG.randint(31, 38), cycle,
                  lambda e, t: cycle[t % 3])


def make_axebot() -> Enemy:
    """Wiki: HP 70-78. Boot Up (gains 10 Block and 3 Strength); The One-Two
    (9 dmg x2); Hammer Uppercut (12 dmg, applies 2 Weak and 2 Frail)."""
    def _boot_up(engine, enemy):
        enemy.gain_block(10)
        enemy.add_status(StatusType.STRENGTH, 3)
    boot_up = Move("Boot Up", IntentType.DEFEND, _boot_up, damage=0)
    one_two = Move("The One-Two", IntentType.ATTACK, _multi_hit(9, 2), damage=9)

    def _uppercut_rider(engine, enemy, target):
        target.add_status(StatusType.WEAK, 2, applier=enemy)
        target.add_status(StatusType.FRAIL, 2, applier=enemy)
    uppercut = Move("Hammer Uppercut", IntentType.ATTACK,
                     _multi_hit(12, 1, _uppercut_rider), damage=12)
    cycle = [boot_up, one_two, uppercut]
    return Enemy("Axebot", CONTENT_RNG.randint(70, 78), cycle, lambda e, t: cycle[t % 3])


def make_zapbot() -> Enemy:
    """Wiki: Minion, HP 18-23. Zap (14 dmg). Built by the Fabricator."""
    zap = Move("Zap", IntentType.ATTACK, _dmg_move(14), damage=14)
    e = Enemy("Zapbot", CONTENT_RNG.randint(18, 23), [zap], lambda en, t: zap)
    e.is_minion = True
    return e


def make_stabbot() -> Enemy:
    """Wiki: Minion, HP 18-23. Stab (11 dmg, applies 1 Frail)."""
    def _frail_rider(engine, enemy, target):
        target.add_status(StatusType.FRAIL, 1, applier=enemy)
    stab = Move("Stab", IntentType.ATTACK, _multi_hit(11, 1, _frail_rider), damage=11)
    e = Enemy("Stabbot", CONTENT_RNG.randint(18, 23), [stab], lambda en, t: stab)
    e.is_minion = True
    return e


def make_guardbot() -> Enemy:
    """Wiki: Minion, HP 16-20. Guard (gives the FABRICATOR 15 Block).

    The first move in the replica where an enemy buffs another enemy by
    name; it falls back to its leader, then to any other living enemy, so
    it still does something if the Fabricator is already dead."""
    def _guard(engine, enemy):
        fab = next((e for e in engine.enemies_alive() if e.name == "Fabricator"), None)
        if fab is None:
            fab = enemy.leader if (enemy.leader and enemy.leader.alive) else None
        if fab is None:
            others = [e for e in engine.enemies_alive() if e is not enemy]
            fab = others[0] if others else enemy
        fab.gain_block(15)
        engine.log.append(f"{enemy.name} gives {fab.name} 15 Block")
    guard = Move("Guard", IntentType.DEFEND, _guard, damage=0)
    e = Enemy("Guardbot", CONTENT_RNG.randint(16, 20), [guard], lambda en, t: guard)
    e.is_minion = True
    return e


def make_noisebot() -> Enemy:
    """Wiki: Minion, HP 18-23. Noise (shuffles 2 Dazed into the player's
    draw and discard piles -- one into each)."""
    def _noise(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.draw_pile.insert(0, make_dazed())
        target.discard_pile.append(make_dazed())
        engine.log.append(f"{target.name} gains 2 Dazed (1 draw pile, 1 discard)")
    noise = Move("Noise", IntentType.DEBUFF, _noise, damage=0)
    e = Enemy("Noisebot", CONTENT_RNG.randint(18, 23), [noise], lambda en, t: noise)
    e.is_minion = True
    return e


def make_fabricator() -> Enemy:
    """Wiki: HP 150. Fabricate (summons 1 defensive bot and 1 aggressive
    bot); Fabricating Strike (18 dmg, summons 1 aggressive bot);
    Disintegrate (11 dmg).

    Defensive = Guardbot or Noisebot, aggressive = Zapbot or Stabbot, both
    picked at random from its own seeded rng."""
    def _aggressive(enemy):
        return enemy.rng.choice([make_zapbot, make_stabbot])()

    def _defensive(enemy):
        return enemy.rng.choice([make_guardbot, make_noisebot])()

    def _fabricate(engine, enemy):
        engine.summon_enemy([_defensive(enemy), _aggressive(enemy)], summoner=enemy)
    fabricate = Move("Fabricate", IntentType.BUFF, _fabricate, damage=0)

    def _fab_strike(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(18), log=engine.log,
                            label=enemy.name, attacker=enemy)
        engine.summon_enemy(_aggressive(enemy), summoner=enemy)
    fab_strike = Move("Fabricating Strike", IntentType.ATTACK, _fab_strike, damage=18)
    disintegrate = Move("Disintegrate", IntentType.ATTACK, _dmg_move(11), damage=11)
    cycle = [fabricate, disintegrate, fab_strike]
    return Enemy("Fabricator", 150, cycle, lambda e, t: cycle[t % 3])


def make_frog_knight() -> Enemy:
    """Wiki: HP 191. Tongue Lash (13 dmg, 2 Frail); Strike Down Evil (21);
    For the Queen (gains 5 Strength); Beetle Charge (35)."""
    def _frail_rider(engine, enemy, target):
        target.add_status(StatusType.FRAIL, 2, applier=enemy)
    tongue = Move("Tongue Lash", IntentType.ATTACK, _multi_hit(13, 1, _frail_rider), damage=13)
    strike_down = Move("Strike Down Evil", IntentType.ATTACK, _dmg_move(21), damage=21)

    def _for_the_queen(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 5)
    for_queen = Move("For the Queen", IntentType.BUFF, _for_the_queen, damage=0)
    charge = Move("Beetle Charge", IntentType.ATTACK, _dmg_move(35), damage=35)
    cycle = [tongue, for_queen, strike_down, charge]
    return Enemy("Frog Knight", 191, cycle, lambda e, t: cycle[t % 4])


def make_globe_head() -> Enemy:
    """Wiki: HP 148. Shocking Slap (13 dmg, 2 Frail); Thunder Strike
    (6 dmg x3); Galvanic Burst (16 dmg, gains 2 Strength)."""
    def _frail_rider(engine, enemy, target):
        target.add_status(StatusType.FRAIL, 2, applier=enemy)
    slap = Move("Shocking Slap", IntentType.ATTACK, _multi_hit(13, 1, _frail_rider), damage=13)
    thunder = Move("Thunder Strike", IntentType.ATTACK, _multi_hit(6, 3), damage=6)

    def _burst_rider(engine, enemy, target):
        enemy.add_status(StatusType.STRENGTH, 2)
    burst = Move("Galvanic Burst", IntentType.ATTACK, _multi_hit(16, 1, _burst_rider), damage=16)
    cycle = [slap, thunder, burst]
    return Enemy("Globe Head", 148, cycle, lambda e, t: cycle[t % 3])


def make_owl_magistrate() -> Enemy:
    """Wiki: HP 234, fixed cycle: Magistrate Scrutiny (16) -> Peck Assault
    (4 x6) -> Judicial Flight (gains Soar) -> Verdict (33 dmg, 4 Vulnerable,
    removes Soar).

    Soar ("receives 50% less attack damage until it lands") is a window
    where hitting it is inefficient -- and it ends on the turn it hits you
    hardest. Unlike Flutter, no stack is spent per hit; only Verdict ends
    it."""
    scrutiny = Move("Magistrate Scrutiny", IntentType.ATTACK, _dmg_move(16), damage=16)
    peck = Move("Peck Assault", IntentType.ATTACK, _multi_hit(4, 6), damage=4)

    def _flight(engine, enemy):
        enemy.add_status(StatusType.SOAR, 1)
        engine.log.append(f"{enemy.name} takes flight (Soar: 50% less attack damage)")
    flight = Move("Judicial Flight", IntentType.DEFEND, _flight, damage=0)

    def _verdict(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(33), log=engine.log,
                            label=enemy.name, attacker=enemy)
        target.add_status(StatusType.VULNERABLE, 4, applier=enemy)
        enemy.statuses.pop(StatusType.SOAR, None)
    verdict = Move("Verdict", IntentType.ATTACK, _verdict, damage=33)
    cycle = [scrutiny, peck, flight, verdict]
    return Enemy("Owl Magistrate", 234, cycle, lambda e, t: cycle[t % 4])


def make_slimed_berserker() -> Enemy:
    """Wiki: HP 266. Vomit Ichor (shuffles TEN Slimed); Furious Pummeling
    (4 dmg x4); Leeching Hug (3 Weak, gains 3 Strength); Smother (30)."""
    def _vomit(engine, enemy):
        _shuffle_status_cards(engine, engine.pick_enemy_attack_target(),
                               make_slimed, 10, "Slimed")
    vomit = Move("Vomit Ichor", IntentType.DEBUFF, _vomit, damage=0)
    pummel = Move("Furious Pummeling", IntentType.ATTACK, _multi_hit(4, 4), damage=4)

    def _hug(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.add_status(StatusType.WEAK, 3, applier=enemy)
        enemy.add_status(StatusType.STRENGTH, 3)
    hug = Move("Leeching Hug", IntentType.DEBUFF, _hug, damage=0)
    smother = Move("Smother", IntentType.ATTACK, _dmg_move(30), damage=30)
    cycle = [vomit, pummel, hug, smother]
    return Enemy("Slimed Berserker", 266, cycle, lambda e, t: cycle[t % 4])


def make_living_shield() -> Enemy:
    """Wiki: HP 55. Shield Slam (6 dmg); Smash (16 dmg, gains 3 Strength).
    Pairs with Turret Operator in its encounter."""
    slam = Move("Shield Slam", IntentType.ATTACK, _dmg_move(6), damage=6)

    def _smash_rider(engine, enemy, target):
        enemy.add_status(StatusType.STRENGTH, 3)
    smash = Move("Smash", IntentType.ATTACK, _multi_hit(16, 1, _smash_rider), damage=16)
    cycle = [slam, smash]
    return Enemy("Living Shield", 55, cycle, lambda e, t: cycle[t % 2])


def make_turret_operator() -> Enemy:
    """Wiki: HP 41. Unload! (3 dmg x5); Loading (gains 1 Strength)."""
    unload = Move("Unload!", IntentType.ATTACK, _multi_hit(3, 5), damage=3)

    def _loading(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 1)
    loading = Move("Loading", IntentType.BUFF, _loading, damage=0)
    cycle = [loading, unload]
    return Enemy("Turret Operator", 41, cycle, lambda e, t: cycle[t % 2])


def make_the_lost() -> Enemy:
    """Wiki: HP 93. Debilitating Smog (removes 2 Strength from the player
    and gains 2 itself); Eye Lasers (4 dmg x2)."""
    def _smog(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.STRENGTH_LOSS, 2, applier=enemy)
        enemy.add_status(StatusType.STRENGTH, 2)
        engine.log.append(f"{enemy.name} drains 2 Strength")
    smog = Move("Debilitating Smog", IntentType.DEBUFF, _smog, damage=0)
    lasers = Move("Eye Lasers", IntentType.ATTACK, _multi_hit(4, 2), damage=4)
    cycle = [smog, lasers]
    return Enemy("The Lost", 93, cycle, lambda e, t: cycle[t % 2])


def make_the_forgotten() -> Enemy:
    """Wiki: HP 106. Miasma (removes 2 Dexterity from the player, gains 8
    Block and 2 Dexterity); Dread (13 dmg plus its own Dexterity).

    Dread scaling off its own Dexterity is unusual -- Dexterity normally
    only affects Block -- so that bonus is computed explicitly here rather
    than falling out of the damage pipeline."""
    def _miasma(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.DEXTERITY_LOSS, 2, applier=enemy)
        enemy.gain_block(8)
        enemy.add_status(StatusType.DEXTERITY, 2)
        engine.log.append(f"{enemy.name} drains 2 Dexterity")
    miasma = Move("Miasma", IntentType.DEBUFF, _miasma, damage=0)

    def _dread(engine, enemy):
        bonus = enemy.get_status(StatusType.DEXTERITY)
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(13 + bonus), log=engine.log,
                            label=enemy.name, attacker=enemy)
    dread = Move("Dread", IntentType.ATTACK, _dread, damage=13)
    cycle = [miasma, dread]
    return Enemy("The Forgotten", 106, cycle, lambda e, t: cycle[t % 2])


# --- Glory elites ----------------------------------------------------------

def make_mecha_knight() -> Enemy:
    """Wiki: Elite, HP 300. Charge (25 dmg); Flamethrower (shuffles 4 Burn
    into your HAND); Windup (gains 15 Block and 5 Strength); Heavy Cleave
    (35 dmg)."""
    charge = Move("Charge", IntentType.ATTACK, _dmg_move(25), damage=25)

    def _flamethrower(engine, enemy):
        target = engine.pick_enemy_attack_target()
        for _ in range(4):
            target.add_to_hand(make_burn(), engine.log)
        engine.log.append(f"{target.name} gains 4 Burn in hand ({enemy.name})")
    flamethrower = Move("Flamethrower", IntentType.DEBUFF, _flamethrower, damage=0)

    def _windup(engine, enemy):
        enemy.gain_block(15)
        enemy.add_status(StatusType.STRENGTH, 5)
    windup = Move("Windup", IntentType.DEFEND, _windup, damage=0)
    cleave = Move("Heavy Cleave", IntentType.ATTACK, _dmg_move(35), damage=35)
    cycle = [charge, flamethrower, windup, cleave]
    return Enemy("Mecha Knight", 300, cycle, lambda e, t: cycle[t % 4], category="elite")


def make_soul_nexus() -> Enemy:
    """Wiki: Elite, HP 234. Soul Burn (29 dmg); Maelstrom (6 dmg x4);
    Drain Life (18 dmg, applies 2 Vulnerable).

    Drain Life's wiki entry truncates after the Vulnerable clause, so only
    the documented half is implemented -- the name suggests it also heals."""
    soul_burn = Move("Soul Burn", IntentType.ATTACK, _dmg_move(29), damage=29)
    maelstrom = Move("Maelstrom", IntentType.ATTACK, _multi_hit(6, 4), damage=6)

    def _drain_rider(engine, enemy, target):
        target.add_status(StatusType.VULNERABLE, 2, applier=enemy)
    drain = Move("Drain Life", IntentType.ATTACK, _multi_hit(18, 1, _drain_rider), damage=18)
    cycle = [maelstrom, drain, soul_burn]
    return Enemy("Soul Nexus", 234, cycle, lambda e, t: cycle[t % 3], category="elite")


def make_knight_gang() -> List[Enemy]:
    """Wiki: Elite, THREE knights, each with a standing rule that lasts only
    while it lives:

    - Flail Knight (101 HP): Breaker (+3 Strength) / Flail (9 x2) / Ram (15).
      Opens on Ram.
    - Spectral Knight (93 HP): "While alive, ALL your cards are Ethereal."
      Hex (applies 2 Hex) / Soul Slash (15) / Soul Flame (3 x3).
    - Magi Knight (82 HP): "While alive, ALL your cards are Downgraded."
      Power Shield (6 dmg, +5 Block) / Dampen (applies Downgraded) / Ram (10)
      / Prep (+5 Block) / Magic Bomb (35).

    Hex IS the Ethereal effect per the wiki's Debuffs page: the hand
    exhausts at end of turn instead of discarding. Downgraded is documented
    nowhere -- read here as "cards resolve as their un-upgraded printing",
    which is the least invented reading of the word."""
    def _breaker(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 3)
    breaker = Move("Breaker", IntentType.BUFF, _breaker, damage=0)
    flail = Move("Flail", IntentType.ATTACK, _multi_hit(9, 2), damage=9)
    ram15 = Move("Ram", IntentType.ATTACK, _dmg_move(15), damage=15)
    flail_cycle = [ram15, flail, breaker, flail]
    flail_knight = Enemy("Flail Knight", 101, flail_cycle,
                          lambda e, t: flail_cycle[t % len(flail_cycle)], category="elite")

    def _hex(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.HEX, 2, applier=enemy)
        engine.log.append(f"{enemy.name} applies 2 Hex (your cards are Ethereal)")
    hex_move = Move("Hex", IntentType.DEBUFF, _hex, damage=0)
    soul_slash = Move("Soul Slash", IntentType.ATTACK, _dmg_move(15), damage=15)
    soul_flame = Move("Soul Flame", IntentType.ATTACK, _multi_hit(3, 3), damage=3)
    spectral_cycle = [hex_move, soul_slash, soul_flame]

    def _spectral_death(engine, enemy):
        for p in engine.players:
            p.statuses.pop(StatusType.HEX, None)
        engine.log.append("Hex fades with the Spectral Knight")
    spectral = Enemy("Spectral Knight", 93, spectral_cycle,
                      lambda e, t: spectral_cycle[t % len(spectral_cycle)], category="elite")
    spectral.on_death = _spectral_death

    def _power_shield_rider(engine, enemy, target):
        enemy.gain_block(5)
    power_shield = Move("Power Shield", IntentType.ATTACK,
                         _multi_hit(6, 1, _power_shield_rider), damage=6)

    def _dampen(engine, enemy):
        for p in engine.players_alive():
            p.add_status(StatusType.DOWNGRADED, 1, applier=enemy)
        engine.log.append(f"{enemy.name} applies Downgraded (cards lose their upgrades)")
    dampen = Move("Dampen", IntentType.DEBUFF, _dampen, damage=0)
    ram10 = Move("Ram", IntentType.ATTACK, _dmg_move(10), damage=10)

    def _prep(engine, enemy):
        enemy.gain_block(5)
    prep = Move("Prep", IntentType.DEFEND, _prep, damage=0)
    magic_bomb = Move("Magic Bomb", IntentType.ATTACK, _dmg_move(35), damage=35)
    magi_tail = [ram10, prep, magic_bomb]

    def magi_choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return power_shield
        if turn == 1:
            return dampen
        return magi_tail[(turn - 2) % len(magi_tail)]

    def _magi_death(engine, enemy):
        for p in engine.players:
            p.statuses.pop(StatusType.DOWNGRADED, None)
        engine.log.append("Downgraded fades with the Magi Knight")
    magi = Enemy("Magi Knight", 82, [power_shield, dampen] + magi_tail,
                  magi_choose, category="elite")
    magi.on_death = _magi_death
    return [flail_knight, spectral, magi]


# --- Glory bosses ----------------------------------------------------------

def make_queen() -> List[Enemy]:
    """Wiki: Boss, HP 400, fighting alongside ONE Torch Head Amalgam (199).

    Opens Puppet Strings (3 Chains of Binding) then You're Mine (99 Frail,
    Weak AND Vulnerable). While the Amalgam lives she only uses Burn Bright
    for Me (buffs it, gains 20 Block); once it dies she Enrages and switches
    to Off with Your Head / Execution / Enrage.

    Chains of Binding: "the first X cards drawn each turn are Afflicted with
    Bound", and only one Bound card may be played per turn -- so the opener
    is a hard cap on your hand for the rest of the fight."""
    amalgam_moves = [
        Move("Strong Tackle", IntentType.ATTACK, _dmg_move(26), damage=26),
        Move("Tackle", IntentType.ATTACK, _dmg_move(18), damage=18),
        Move("Beam", IntentType.ATTACK, _multi_hit(8, 3), damage=8),
        Move("Weak Tackle", IntentType.ATTACK, _dmg_move(14), damage=14),
    ]
    amalgam = Enemy("Torch Head Amalgam", 199, amalgam_moves,
                     lambda e, t: amalgam_moves[t % len(amalgam_moves)], category="boss")

    def _puppet_strings(engine, enemy):
        for p in engine.players_alive():
            p.chains_of_binding = 3
        engine.log.append(f"{enemy.name} applies 3 Chains of Binding")
    puppet = Move("Puppet Strings", IntentType.DEBUFF, _puppet_strings, damage=0)

    def _youre_mine(engine, enemy):
        for p in engine.players_alive():
            for s in (StatusType.FRAIL, StatusType.WEAK, StatusType.VULNERABLE):
                p.add_status(s, 99, applier=enemy)
        engine.log.append(f"{enemy.name}: 99 Frail, Weak and Vulnerable to all players")
    youre_mine = Move("You're Mine", IntentType.DEBUFF, _youre_mine, damage=0)

    def _burn_bright(engine, enemy):
        if amalgam.alive:
            amalgam.add_status(StatusType.STRENGTH, 1)
        enemy.gain_block(20)
    burn_bright = Move("Burn Bright for Me", IntentType.DEFEND, _burn_bright, damage=0)
    off_with = Move("Off with Your Head", IntentType.ATTACK, _multi_hit(3, 5), damage=3)
    execution = Move("Execution", IntentType.ATTACK, _dmg_move(15), damage=15)

    def _enrage(engine, enemy):
        enemy.add_status(StatusType.STRENGTH, 2)
    enrage = Move("Enrage", IntentType.BUFF, _enrage, damage=0)
    enraged_cycle = [off_with, execution, enrage]

    def queen_choose(enemy: Enemy, turn: int) -> Move:
        if turn == 0:
            return puppet
        if turn == 1:
            return youre_mine
        if amalgam.alive:
            return burn_bright
        i = getattr(enemy, "enraged_turn", None)
        if i is None:
            enemy.enraged_turn = 0
            return enrage
        enemy.enraged_turn = i + 1
        return enraged_cycle[i % len(enraged_cycle)]

    queen = Enemy("Queen", 400, [puppet, youre_mine, burn_bright] + enraged_cycle,
                   queen_choose, category="boss")
    amalgam.leader = None   # NOT a minion: killing the Queen shouldn't remove it
    return [queen, amalgam]


def make_test_subject() -> Enemy:
    """Wiki: Boss, three phases with SEPARATE HP pools: 100 -> 200 -> 300.
    "Adaptable" prevents death and revives it into the next phase.

    Phase 1: Bite (20) / Skull Bash (14, 1 Vulnerable).
    Phase 2: Multi-Claw every turn, 10 damage x3 and gaining a hit each use.
             Painful Stabs adds a Wound to your discard on unblocked damage.
    Phase 3: Lacerate (10 x3) / Big Pounce (45) / Burning Growl (3 Burn,
             +2 Strength). Nemesis grants 1 Intangible every other turn.
             Only here can it be killed for good."""
    bite = Move("Bite", IntentType.ATTACK, _dmg_move(20), damage=20)

    def _skull_rider(engine, enemy, target):
        target.add_status(StatusType.VULNERABLE, 1, applier=enemy)
    skull_bash = Move("Skull Bash", IntentType.ATTACK, _multi_hit(14, 1, _skull_rider), damage=14)
    p1 = [bite, skull_bash]

    def _multi_claw(engine, enemy):
        hits = 3 + getattr(enemy, "claw_uses", 0)
        enemy.claw_uses = getattr(enemy, "claw_uses", 0) + 1
        target = engine.pick_enemy_attack_target()
        for _ in range(hits):
            if not target.alive:
                break
            target.take_damage(enemy.deal_attack_damage(10), log=engine.log,
                                label=enemy.name, attacker=enemy)
    multi_claw = Move("Multi-Claw", IntentType.ATTACK, _multi_claw, damage=10)

    lacerate = Move("Lacerate", IntentType.ATTACK, _multi_hit(10, 3), damage=10)
    big_pounce = Move("Big Pounce", IntentType.ATTACK, _dmg_move(45), damage=45)

    def _growl(engine, enemy):
        _shuffle_status_cards(engine, engine.pick_enemy_attack_target(),
                               make_burn, 3, "Burn")
        enemy.add_status(StatusType.STRENGTH, 2)
    growl = Move("Burning Growl", IntentType.DEBUFF, _growl, damage=0)
    p3 = [lacerate, big_pounce, growl]

    def choose(enemy: Enemy, turn: int) -> Move:
        phase = getattr(enemy, "phase", 1)
        if phase == 1:
            return p1[turn % len(p1)]
        if phase == 2:
            return multi_claw
        # Nemesis: 1 Intangible every other turn in the final phase.
        i = getattr(enemy, "p3_turn", 0)
        enemy.p3_turn = i + 1
        if i % 2 == 1:
            enemy.add_status(StatusType.INTANGIBLE, 1)
        return p3[i % len(p3)]

    def _adaptable(engine, enemy):
        phase = getattr(enemy, "phase", 1)
        if phase >= 3:
            return   # final phase: it stays dead
        enemy.phase = phase + 1
        enemy.max_hp = 200 if enemy.phase == 2 else 300
        enemy.hp = enemy.max_hp
        enemy.alive = True
        enemy.death_resolved = False
        enemy.turn_count = 0
        if enemy.phase == 2:
            enemy.painful_stabs = 1
        else:
            enemy.painful_stabs = 0
        engine.log.append(
            f"{enemy.name} adapts: phase {enemy.phase} with {enemy.max_hp} HP")

    e = Enemy("Test Subject", 100, p1 + [multi_claw] + p3, choose, category="boss")
    e.phase = 1
    e.on_death = _adaptable
    return e


def make_aeonglass() -> Enemy:
    """Wiki: Boss, HP 512. Ebb (22 dmg, gains 33 Block) / Eye Lasers
    (11 dmg x2) / Increasing Intensity.

    Increasing Intensity escalates: the Nth use shuffles a Wither+N into
    your deck and grants 2+N Strength, so the fight gets worse on a timer
    from both directions at once."""
    def _ebb(engine, enemy):
        target = engine.pick_enemy_attack_target()
        target.take_damage(enemy.deal_attack_damage(22), log=engine.log,
                            label=enemy.name, attacker=enemy)
        enemy.gain_block(33)
    ebb = Move("Ebb", IntentType.ATTACK, _ebb, damage=22)
    lasers = Move("Eye Lasers", IntentType.ATTACK, _multi_hit(11, 2), damage=11)

    def _intensity(engine, enemy):
        x = getattr(enemy, "intensity_uses", 0)
        enemy.intensity_uses = x + 1
        target = engine.pick_enemy_attack_target()
        target.discard_pile.append(make_wither(x))
        enemy.add_status(StatusType.STRENGTH, 2 + x)
        engine.log.append(
            f"{enemy.name} intensifies: Wither+{x} added, gains {2 + x} Strength")
    intensity = Move("Increasing Intensity", IntentType.DEBUFF, _intensity, damage=0)
    cycle = [ebb, lasers, intensity]
    return Enemy("Aeonglass", 512, cycle, lambda e, t: cycle[t % 3], category="boss")


def make_doormaker() -> Enemy:
    """Wiki: HP 489, listed under Glory bosses. Dramatic Open (transforms
    and sets its buff to Hunger), then rotates: Hunger (30 dmg -> Scrutiny)
    / Scrutiny (24 dmg -> Grasp) / Grasp (10 dmg x2, gains 3 Strength ->
    Hunger).

    The wiki's Glory boss list names Queen, Test Subject and Aeonglass, so
    it is unclear whether Doormaker is a fourth boss or a transformation of
    one of them. Ported standalone and flagged rather than guessed at."""
    def _open(engine, enemy):
        engine.log.append(f"{enemy.name} opens dramatically (next: Hunger)")
    dramatic = Move("Dramatic Open", IntentType.BUFF, _open, damage=0)
    hunger = Move("Hunger", IntentType.ATTACK, _dmg_move(30), damage=30)
    scrutiny = Move("Scrutiny", IntentType.ATTACK, _dmg_move(24), damage=24)

    def _grasp_rider(engine, enemy, target):
        enemy.add_status(StatusType.STRENGTH, 3)
    grasp = Move("Grasp", IntentType.ATTACK, _multi_hit(10, 2, _grasp_rider), damage=10)
    rotation = [hunger, scrutiny, grasp]

    def choose(enemy: Enemy, turn: int) -> Move:
        return dramatic if turn == 0 else rotation[(turn - 1) % len(rotation)]

    return Enemy("Doormaker", 489, [dramatic] + rotation, choose, category="boss")
