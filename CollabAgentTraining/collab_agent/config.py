"""All constants and the reward weights in one place."""
from dataclasses import dataclass, field, asdict
import json

# ---------------------------------------------------------------- layout
N_PLAYERS = 4          # slot 0 = the agent, slots 1-3 = teammates
N_ENEMIES = 6
HAND_SIZE = 10
N_CHOICE = 3           # K choice slots (Divide and Conquer)
N_TARGETS = 10         # 0 = agent, 1-3 = teammates, 4-9 = enemies

# action indices
A_END = 0
A_PLAY0 = 1            # 1 + 10*h + t
A_CHOOSE0 = 101        # 101 + k
A_STOP = 104
A_WAIT = 105
N_ACTIONS = 106

# ---------------------------------------------------------------- statuses (S = 74, engine order)
STATUS_LIST = (
    "aggression artifact automation barricade beacon_of_hope block_lockout bomb calamity "
    "caltrops choking colossus_guard constrict corruption crimson_mantle cruelty curious "
    "dark_embrace delayed_block delayed_draw delayed_energy demon_form dexterity enlightenment "
    "entropy exposed fasten feel_no_pain flame_barrier frail free_attack gambit hello_world "
    "hellraiser illusion inferno infested intangible intercepting juggernaut juggling mayhem "
    "minion no_energy_gain no_more_draw nostalgia one_two_punch panache plating prep_time "
    "protected pyre rage rebound return_to_hand rolling_boulder rupture sandpit shrink stampede "
    "stored_block stratagem strength strength_loss_this_turn strength_this_turn stun tag_team "
    "tangled tank unmovable vicious vigor vulnerable weak withering_presence"
).split()
assert len(STATUS_LIST) == 74
S = len(STATUS_LIST)
STATUS_INDEX = {name: i for i, name in enumerate(STATUS_LIST)}

# on/off statuses (1 / 0); everything else is a count status
FLAG_STATUSES = {"barricade", "corruption", "minion", "no_more_draw", "no_energy_gain", "unmovable"}
# STATUS_REF: default 3, higher for statuses that usually stack high
STATUS_REF_DEFAULT = 3.0
STATUS_REF = {"strength": 6.0, "dexterity": 6.0, "plating": 6.0, "vigor": 6.0}
DEBUFFS = {"vulnerable", "weak", "frail"}
BUFFS = {"strength", "dexterity", "plating", "vigor"}

# ---------------------------------------------------------------- normalization constants
REF_ALLY_HP = 80.0
ALLY_SCALE_RANGE = 4.0
REF_ENEMY_HP = 100.0
ENEMY_SCALE_RANGE = 5.0
REF_ENERGY = 3.0
REF_BLOCK = 5.0
REF_DAMAGE = 10.0
REF_HITS = 2.0
REF_TURNS = 5.0
REF_PILE_SIZE = 10.0

# ---------------------------------------------------------------- input sizes
GLOBAL_SIZE = 5
PLAYER_SIZE = 9 + S + 6          # 89
ENEMY_SIZE = 5 + S + 7           # 86
OUTCOME_SIZE = 3 + S             # 77
CARD_SIZE = 19 + 4 * OUTCOME_SIZE  # 327
N_CARD_SLOTS = N_PLAYERS * HAND_SIZE + N_CHOICE  # 43
PILE_SIZE = 9
N_PILES = 3

OFF_GLOBAL = 0
OFF_PLAYERS = OFF_GLOBAL + GLOBAL_SIZE
OFF_ENEMIES = OFF_PLAYERS + N_PLAYERS * PLAYER_SIZE
OFF_CARDS = OFF_ENEMIES + N_ENEMIES * ENEMY_SIZE
OFF_PILES = OFF_CARDS + N_CARD_SLOTS * CARD_SIZE
OBS_SIZE = OFF_PILES + N_PLAYERS * N_PILES * PILE_SIZE
assert OBS_SIZE == 15046, OBS_SIZE

# card effects (EnvConfig.card_effects): what a card does that its damage, Block and statuses don't show, one block of
# EFFECT_SIZE numbers per card slot written after the piles, so every offset above stays the same. HP the holder loses and
# heals, energy and cards it gains, energy and cards a teammate gains (soft-scaled), then 1 / 0 for: exhausts, adds, moves,
# improves (upgrade, boost, cost) its own cards, plays other cards.
EFFECT_NAMES = ("hp_lost", "healed", "energy", "draws", "mate_energy", "mate_draws",
                "exhausts", "adds", "moves", "improves", "plays")
EFFECT_SIZE = len(EFFECT_NAMES)  # 11
N_EFFECT_COUNTS = 6              # the first six are counts, the rest flags
OFF_EFFECTS = OBS_SIZE
OBS_SIZE_EFFECTS = OBS_SIZE + N_CARD_SLOTS * EFFECT_SIZE   # 15,519
REF_HP_COST = 6.0
REF_HEAL = 10.0
REF_DRAW = 3.0


# enemy statuses (EnvConfig.enemy_statuses): Act 1 enemies' own statuses that STATUS_LIST lacks, so without this they never
# reach the input. ENEMY_EXTRA_SIZE numbers per enemy slot, after the piles and any card effects, so no offset above moves;
# scaled as write_statuses scales a count status, Steam Eruption on its own scale (it is the Waterfall Giant's blast to come).
ENEMY_EXTRA_STATUSES = ("asleep", "hardened_shell", "plow", "ringing", "shriek", "skittish", "slippery", "slow",
                        "steam_eruption", "territorial")
ENEMY_EXTRA_SIZE = len(ENEMY_EXTRA_STATUSES)     # 10
ENEMY_EXTRA_REF = {"steam_eruption": 20.0}
assert not set(ENEMY_EXTRA_STATUSES) & set(STATUS_LIST)


def enemy_extra_offset(card_effects):
    """Where the enemy-status block starts: after the piles, and after the card effects when there are any."""
    return OBS_SIZE_EFFECTS if card_effects else OBS_SIZE


def obs_size(cfg):
    """The input's length for an EnvConfig: 15,046; 15,519 with card_effects; 60 more with enemy_statuses."""
    effects = getattr(cfg, "card_effects", False)
    return enemy_extra_offset(effects) + (N_ENEMIES * ENEMY_EXTRA_SIZE if getattr(cfg, "enemy_statuses", False) else 0)


# ---------------------------------------------------------------- reward weights
@dataclass
class RewardWeights:
    own_damage: float = 1.0       # agent's damage / total enemy max HP at fight start
    teammate_damage: float = 0.5  # teammates' damage / total enemy max HP
    kill: float = 0.1             # per enemy the agent kills
    useful_block: float = 0.5     # Block that covers an incoming hit / that player's max HP
    hp_lost: float = 1.0          # penalty: mean over players of HP lost / max HP
    knockout: float = 0.5         # penalty per player knocked out
    round: float = 0.01           # penalty per round that passes
    win: float = 1.0
    lose: float = 1.0

    @classmethod
    def load(cls, path):
        with open(path) as f:
            return cls(**json.load(f))

    def save(self, path):
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)


from .final_reward import FinalRewardConfig  # noqa: E402

# ---------------------------------------------------------------- environment settings
@dataclass
class EnvConfig:
    # "mock": the stand-in engine (engine.py, fast, made-up cards); "real": the 2nd_model engine
    # through real_engine.py (the game's cards and Act 1 enemies; 2nd_model next to this folder)
    engine: str = "mock"
    real_ally: str = "ironclad"               # real engine: every player's character
    real_extra_cards: int = 4                 # real engine: cards on top of the starter deck (real_engine.card_pool)
    real_deck: tuple = None                   # real engine: every seat plays exactly this deck (real_engine.FIXED_DECKS)
    # real engine, with real_deck: each new team is dealt one of these kinds of deck, drawn at random. "Whole": every seat
    # the whole real_deck. A preset (real_engine.DECK_PRESETS): each seat its own deck, cards drawn from real_deck's
    real_deck_presets: tuple = None
    real_pool_cards: int = 8                  # real engine, a "Pool" deck (real_deck_presets): pool cards on top of the starter
    history_fights: int = 0                  # fights a new team plays before the agent meets it, so its profiles start built
    real_pool_weights: tuple = (0.7, 0.2, 0.1)   # real engine: hallway, elite, boss fights
    # real engine: shares of max HP, one drawn for each player at each fight start (None: everyone full)
    start_hp: tuple = None
    min_teammates: int = 1
    max_teammates: int = 3
    # teammate bot types sampled for each new team (see bots.py)
    teammate_types: tuple = ("aggressive", "defensive", "cheese", "random", "change", "support")
    # a team stays together for this many fights; profiles carry over between them
    team_fights: int = 10
    # profiles live in memory; a folder here also saves each as a JSON file (slower; for looking at)
    profile_dir: str = None
    teammate_lead_prob: float = 0.3   # chance each teammate acts before the agent at turn start
    enemy_hp_per_player: float = 125.0   # difficulty: enemy HP budget per player
    enemy_atk_per_player: float = 15.0  # difficulty: enemy attack per player per round
    max_rounds: int = 30              # fight is a loss after this many rounds
    zero_profiles: bool = False       # ablation: hide teammate profiles from the agent
    # tests of what a profile is worth when the agent has to move before seeing its teammates' plays:
    # no_wait: no Wait and teammates never act first; their hands stay visible
    # blind_teammates: the same, and their hands and piles are hidden (health, Block, energy, statuses stay)
    no_wait: bool = False
    blind_teammates: bool = False
    # the agent's input and targets list teammates by danger at every decision: slot 1 is the one most at risk
    # (the HP they would have left after the hits coming at them), knocked-out teammates last. False: by seat
    sort_teammates: bool = False
    # the agent's network: "flat" (model.py, one output per action) or "pair" (pair_policy.py, one scorer for
    # every card-and-target pair). Only training reads it; it is kept here so a run's config.json says which
    network: str = "flat"
    # real engine, "pair" network: each card in the input also shows what its damage, Block and statuses don't (HP it costs,
    # healing, energy, draw, the same for a teammate, what it does to its own cards: config.EFFECT_NAMES). False: as before
    card_effects: bool = False
    # real engine: the enemies' statuses that STATUS_LIST lacks (ENEMY_EXTRA_STATUSES: the Waterfall Giant's Steam Eruption,
    # Lagavulin's Asleep, ...) in a block of their own at the end of the input. False: as before, where they are dropped
    enemy_statuses: bool = False
    # Advantage_point test: show the agent each teammate's A, S, T as the style furthest
    # from theirs (style_profiles, from styles.py); confidence and the reward stay true
    swap_profiles: bool = False
    style_profiles: dict = None
    reward_mode: str = "final"        # "final" = Final_reward_norm, "weighted" = RewardWeights
    final: FinalRewardConfig = field(default_factory=FinalRewardConfig)
    reward: RewardWeights = field(default_factory=RewardWeights)
