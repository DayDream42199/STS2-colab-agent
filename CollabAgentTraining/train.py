"""Train the Collaborative Agent with MaskablePPO.

Default reward: Final_reward_norm (collab_agent/final_reward.py), paid as the change each step
    python train.py
    python train.py --penalty 45,20,20,15,10 --turn 6,10,0.35      # A,B,C,D (= 100) and E on top
    python train.py --scoring variant2 --cdecay 0.5                # its starting weights
    python train.py --scoring variant1 --collab-w 0.4,0.2,0        # or your own
    python train.py --penalty 35,5,5,15,5 --team-penalty 15,25     # teammates' HP and knockouts apart from the agent's
    python train.py --collab-w 0,0,0                               # collaboration off
    python train.py --timesteps 5000000 --n-envs 8 --subproc
    python train.py --engine real                                  # on 2nd_model's engine
    python train.py --teammates aggressive                         # only these bots as teammates
    python train.py --engine real --deck teamwork                  # every seat the same whole deck
    python train.py --engine real --extra-cards 14                 # bigger random decks
    python train.py --engine real --deck teamwork --deck-presets Whole,Default,Small,Bloated,Helper   # varied decks
    python train.py --engine real --deck teamwork --deck-presets Whole,Default,Pool --pool-cards 8    # and pool cards
    python train.py --engine real --pool-weights 0,0.5,0.5         # elite and boss fights only
    python train.py --teammates continuous --history-fights 10     # teams that already have a profile
    python train.py --no-wait                                      # test: the agent moves before its teammates
    python train.py --blind-teammates                              # test: the same, teammates' cards hidden too
    python train.py --engine real --start-hp 100,75,50,25,10       # each player's HP drawn separately each fight
    python train.py --sort-teammates                               # slot 1 is always the teammate most at risk
    python train.py --network pair                                 # one scorer for every card-and-target pair
    python train.py --engine real --network pair --card-effects    # cards also show HP cost, energy, draw, ...

Old weighted reward:
    python train.py --reward-mode weighted --reward-config reward_weights.json

TensorBoard:  tensorboard --logdir runs        (every run also writes <out>/progress.csv)
"""
import argparse
import json
import os
from dataclasses import asdict

import numpy as np
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback, CheckpointCallback
from stable_baselines3.common.logger import configure
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecMonitor, VecNormalize

from collab_agent.bots import BOT_KINDS
from collab_agent.config import EnvConfig, RewardWeights
from collab_agent.final_reward import FinalRewardConfig, PenaltyWeights, CollabSettings, DEFAULT_WEIGHTS, SCORINGS
from collab_agent.env import CollabEnv
from collab_agent.model import CardReaderExtractor
from collab_agent.pair_policy import PairExtractor, PairPolicy

NETWORKS = ("flat", "pair")


class TrainingCallback(BaseCallback):
    """Tells the envs the current timestep (CTime) and logs every reward part per fight."""

    def __init__(self):
        super().__init__()
        self.buf = []
        self.max_abs = 0.0

    def _on_rollout_start(self):
        self.training_env.env_method("set_ctime", self.num_timesteps)

    def _on_step(self):
        for info in self.locals["infos"]:
            if "episode_summary" in info:
                self.buf.append(info["episode_summary"])
        if hasattr(self.training_env, "get_original_reward"):        # the reward before VecNormalize
            self.max_abs = max(self.max_abs, float(np.abs(self.training_env.get_original_reward()).max()))
        return True

    def _on_rollout_end(self):
        # Reward health: one step far past +-1 sets VecNormalize's scale for the rest of training
        # and every later reward shrinks to nothing (a Waterfall Giant's 999,999,999 HP once did).
        self.logger.record("reward/max_abs_step", self.max_abs)
        self.max_abs = 0.0
        if hasattr(self.training_env, "ret_rms"):
            self.logger.record("reward/norm_std", float(np.sqrt(self.training_env.ret_rms.var)))
        if not self.buf:
            return
        keys = [k for k, v in self.buf[0].items() if isinstance(v, (int, float))]
        for k in keys:
            group = "fight" if k in ("win", "rounds", "ret", "ally_hp_frac", "score", "assist_share", "self_alive",
                                     "mates_alive", "score_std") else "reward"
            self.logger.record(f"{group}/{k}", float(np.mean([s.get(k, 0.0) for s in self.buf])))
        self.buf = []


def make_env(cfg, seed):
    def _init():
        return CollabEnv(cfg, seed=seed)
    return _init


def floats(text, n):
    vals = [float(x) for x in text.split(",")]
    if len(vals) != n:
        raise argparse.ArgumentTypeError(f"expected {n} comma-separated numbers, got {text!r}")
    return vals


def percents(text):
    """'100,75,50' -> (1.0, 0.75, 0.5)"""
    return tuple(float(x) / 100 for x in text.split(","))


def build_config(penalty=(45, 15, 25, 15, 5), turn=(6, 10, 0.35), scoring="baseline",
                 collab_w=None, cdecay=0.5, timesteps=2_000_000, reward_mode="final",
                 reward_weights=None, zero_profiles=False, profile_dir=None, engine="mock", teammates=None,
                 deck=None, extra_cards=None, history_fights=0, pool_weights=None, no_wait=False, blind_teammates=False,
                 start_hp=None, team_penalty=None, sort_teammates=False, network="flat", deck_presets=None, pool_cards=None,
                 card_effects=False, enemy_statuses=False):
    """collab_w None: the scoring's starting weights (final_reward.DEFAULT_WEIGHTS).
    teammates None: the default mix, EnvConfig.teammate_types.
    deck: a name in real_engine.FIXED_DECKS; extra_cards: random cards on top of the starter.
    deck_presets: with deck, the kinds of deck a new team may be dealt (real_engine.WHOLE_DECK, POOL_DECK, DECK_PRESETS).
    pool_cards: with Pool among deck_presets, the pool cards on its starter (default EnvConfig.real_pool_cards).
    history_fights: fights a new team plays first, so the agent meets it with built profiles.
    pool_weights: the shares of hallway, elite and boss fights.
    no_wait, blind_teammates: see EnvConfig.
    start_hp: shares of max HP, one drawn for each player at each fight start; None: everyone full.
    team_penalty: (B_team, C_team): teammates' HP and knockouts on their own weights, B and C the agent's own.
    sort_teammates, network, card_effects, enemy_statuses: see EnvConfig."""
    if network not in NETWORKS:
        raise ValueError(f"unknown network {network!r}: one of {', '.join(NETWORKS)}")
    if card_effects and (engine != "real" or network != "pair"):
        raise ValueError("--card-effects reads the real engine's cards into the pair network: it needs --engine real "
                         "and --network pair")
    if enemy_statuses and (engine != "real" or network != "pair"):
        raise ValueError("--enemy-statuses reads the real engine's enemies into the pair network: it needs --engine real "
                         "and --network pair")
    if scoring not in SCORINGS:
        raise ValueError(f"unknown scoring {scoring!r}: one of {', '.join(SCORINGS)}")
    real = {}
    if deck is not None and extra_cards is not None:
        raise ValueError("--deck is a whole deck: it cannot take --extra-cards too")
    if engine != "real" and (deck is not None or extra_cards is not None or pool_weights is not None or start_hp):
        raise ValueError("--deck, --extra-cards, --pool-weights and --start-hp need --engine real")
    if deck is not None:
        from collab_agent.real_engine import FIXED_DECKS   # here: it needs 2nd_model next to this folder
        if deck not in FIXED_DECKS:
            raise ValueError(f"unknown deck {deck!r}: one of {', '.join(FIXED_DECKS)}")
        real["real_deck"] = FIXED_DECKS[deck]
    if deck_presets:
        if deck is None:
            raise ValueError("--deck-presets deals from a whole deck: it needs --deck")
        from collab_agent.real_engine import DECK_PRESETS, POOL_DECK, WHOLE_DECK, card_kinds
        names = {name.lower(): name for name in (WHOLE_DECK, POOL_DECK, *DECK_PRESETS)}
        unknown = [p for p in deck_presets if p.lower() not in names]
        if unknown:
            raise ValueError(f"unknown deck presets {unknown}: from {', '.join(names.values())}")
        deck_presets = tuple(names[p.lower()] for p in deck_presets)
        kinds = card_kinds(real["real_deck"])
        lacking = sorted({kind for p in deck_presets if p in DECK_PRESETS for kind in DECK_PRESETS[p] if kind not in kinds})
        if lacking:
            raise ValueError(f"deck {deck!r} has no {', '.join(lacking)} card, which these presets deal")
        real["real_deck_presets"] = deck_presets
    if pool_cards is not None:
        from collab_agent.real_engine import POOL_DECK, card_pool
        if POOL_DECK not in (real.get("real_deck_presets") or ()):
            raise ValueError("--pool-cards sets the Pool deck: it needs Pool in --deck-presets")
        if not 0 <= pool_cards <= len(card_pool()):
            raise ValueError(f"--pool-cards takes 0 to {len(card_pool())} cards, got {pool_cards}")
        real["real_pool_cards"] = pool_cards
    if extra_cards is not None:
        real["real_extra_cards"] = extra_cards
    if pool_weights is not None:
        if min(pool_weights) < 0 or sum(pool_weights) <= 0:
            raise ValueError(f"--pool-weights needs shares of at least 0 that add up to more than 0, got {pool_weights}")
        real["real_pool_weights"] = tuple(pool_weights)
    if start_hp:
        if not all(0 < share <= 1 for share in start_hp):
            raise ValueError(f"--start-hp needs percentages above 0 and up to 100, got {[s * 100 for s in start_hp]}")
        real["start_hp"] = tuple(start_hp)
    teammates = tuple(teammates) if teammates else EnvConfig.teammate_types
    if not set(teammates) <= set(BOT_KINDS):
        raise ValueError(f"unknown teammates {teammates}: from {', '.join(BOT_KINDS)}")
    A, B, C, D, E = penalty
    a, b, c = turn
    final = FinalRewardConfig(
        penalty=PenaltyWeights(A, B, C, D, E, a, b, c, *(team_penalty or (None, None))).check(),
        collab=CollabSettings(scoring, *(collab_w if collab_w is not None else DEFAULT_WEIGHTS[scoring]),
                              cdecay=cdecay),
        total_timesteps=timesteps,
    )
    return EnvConfig(engine=engine, reward_mode=reward_mode, final=final, reward=reward_weights or RewardWeights(),
                     zero_profiles=zero_profiles, profile_dir=profile_dir, teammate_types=teammates,
                     history_fights=history_fights, no_wait=no_wait, blind_teammates=blind_teammates,
                     sort_teammates=sort_teammates, network=network, card_effects=card_effects,
                     enemy_statuses=enemy_statuses, **real)


def train(cfg, timesteps, out, n_envs=8, seed=0, subproc=False, resume=None, verbose=1):
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "config.json"), "w") as f:
        json.dump(asdict(cfg), f, indent=2)

    vec_cls = SubprocVecEnv if subproc else DummyVecEnv
    venv = vec_cls([make_env(cfg, seed * 1000 + i) for i in range(n_envs)])
    venv = VecMonitor(venv)
    # reward normalization helps PPO; observations are already normalized (norm_obs=False)
    venv = VecNormalize(venv, norm_obs=False, norm_reward=True, gamma=0.995)

    # Every number logged goes to <out>/progress.csv, and to TensorBoard when it is installed
    # (Stable-Baselines3 refuses to start if TensorBoard is asked for and missing).
    formats = (["stdout"] if verbose else []) + ["csv"]
    try:
        import tensorboard  # noqa: F401
        formats.append("tensorboard")
    except ImportError:
        print(f"tensorboard is not installed: logging to {os.path.join(out, 'progress.csv')} only "
              "(pip install tensorboard for the graphs)")

    if resume:
        model = MaskablePPO.load(resume, env=venv)
    else:
        policy, policy_kwargs = (PairPolicy, dict(features_extractor_class=PairExtractor)) if cfg.network == "pair" else (
            "MlpPolicy", dict(features_extractor_class=CardReaderExtractor, net_arch=dict(pi=[256, 256], vf=[256, 256])))
        model = MaskablePPO(
            policy, venv,
            policy_kwargs=policy_kwargs,
            n_steps=512, batch_size=512, n_epochs=4, learning_rate=3e-4,
            gamma=0.995, gae_lambda=0.95, clip_range=0.2, ent_coef=0.01,
            vf_coef=0.5, max_grad_norm=0.5, seed=seed, verbose=verbose,
        )
    model.set_logger(configure(out, formats))

    callbacks = [
        TrainingCallback(),
        CheckpointCallback(save_freq=max(1, 200_000 // n_envs), save_path=os.path.join(out, "checkpoints"),
                           name_prefix="collab", save_vecnormalize=True),
    ]
    model.learn(total_timesteps=timesteps, callback=callbacks, reset_num_timesteps=resume is None)
    path = os.path.join(out, "final_model")
    model.save(path)
    venv.save(os.path.join(out, "vecnormalize.pkl"))
    venv.close()
    return path + ".zip"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timesteps", type=int, default=2_000_000)
    ap.add_argument("--n-envs", type=int, default=8)
    ap.add_argument("--subproc", action="store_true", help="run envs in separate processes (faster on multi-core)")
    ap.add_argument("--out", default="runs/collab_agent")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--resume", default=None, help="path to a saved model .zip to continue training")
    ap.add_argument("--zero-profiles", action="store_true", help="ablation: hide teammate profiles")
    ap.add_argument("--engine", default="mock", choices=["mock", "real"],
                    help="mock: the stand-in engine; real: 2nd_model's engine (collab_agent/real_engine.py)")
    ap.add_argument("--teammates", default=None,
                    help="only these bot types as teammates, e.g. aggressive or aggressive,blend "
                         f"(from {', '.join(BOT_KINDS)}; default: all but blend)")
    ap.add_argument("--deck", default=None, help="real engine: every seat plays this whole deck, e.g. teamwork "
                                                 "(real_engine.FIXED_DECKS; default: random extra cards)")
    ap.add_argument("--extra-cards", type=int, default=None,
                    help="real engine: random cards on top of the starter deck (default: 4)")
    ap.add_argument("--deck-presets", default=None,
                    help="with --deck: each new team is dealt one of these kinds of deck at random, e.g. "
                         "Whole,Default,Small,Bloated,Helper. Whole: every seat the whole deck; the others: each seat its "
                         "own deck, cards drawn from the whole deck's; Pool: each seat the starter and --pool-cards cards "
                         "from every Ironclad and co-op card; repeat one to make it more common (default: Whole)")
    ap.add_argument("--pool-cards", type=int, default=None,
                    help="with Pool in --deck-presets: the pool cards on its starter deck (default: 8)")
    ap.add_argument("--pool-weights", default=None,
                    help="real engine: shares of hallway,elite,boss fights, e.g. 0,0.5,0.5 (default: 0.7,0.2,0.1)")
    ap.add_argument("--history-fights", type=int, default=0,
                    help="fights a new team plays before the agent meets it, so its profiles start built (default: 0, fresh)")
    ap.add_argument("--no-wait", action="store_true",
                    help="test: no Wait and teammates never act first; their hands stay visible")
    ap.add_argument("--blind-teammates", action="store_true",
                    help="test: as --no-wait, and their hands and piles are hidden")
    ap.add_argument("--network", default="flat", choices=NETWORKS,
                    help="flat: one output per action; pair: one small network scores every card-and-target pair")
    ap.add_argument("--sort-teammates", action="store_true",
                    help="the agent's input and targets list teammates by danger at every decision: "
                         "slot 1 is the one most at risk (default: by seat)")
    ap.add_argument("--card-effects", action="store_true",
                    help="real engine, --network pair: each card in the agent's input also shows what its damage, Block "
                         "and statuses don't: HP it costs, healing, energy, cards drawn, the same for a teammate, and "
                         "whether it exhausts, adds, moves, improves or plays cards (default: off)")
    ap.add_argument("--enemy-statuses", action="store_true",
                    help="real engine: the agent's input also shows the Act 1 enemies' own statuses it otherwise drops (the "
                         "Waterfall Giant's Steam Eruption, Lagavulin's Asleep, ...: config.ENEMY_EXTRA_STATUSES) (default: off)")
    ap.add_argument("--start-hp", default=None,
                    help="real engine: each player's HP at each fight start, drawn separately from these percentages "
                         "of max HP, e.g. 100,75,50,25,10; repeat one to make it more common (default: everyone full)")
    # Final_reward_norm
    ap.add_argument("--penalty", default="45,15,25,15,5", help="A,B,C,D,E: A+B+C+D = 100, E on top")
    ap.add_argument("--team-penalty", default=None,
                    help="B_team,C_team: teammates' HP and knockouts on their own weights; B and C are then the "
                         "agent's own, and A+B+C+D+B_team+C_team = 100 (default: B and C cover the whole team)")
    ap.add_argument("--turn", default="6,10,0.35", help="a,b,c of the turn-count sigmoid")
    ap.add_argument("--scoring", default="baseline", choices=list(SCORINGS), help="collaborative scoring f_n")
    ap.add_argument("--collab-w", default=None,
                    help="w_offense,w_defense,w_others (default: the scoring's starting weights; 0,0,0 = off)")
    ap.add_argument("--cdecay", type=float, default=0.5)
    # old weighted reward
    ap.add_argument("--reward-mode", default="final", choices=["final", "weighted"])
    ap.add_argument("--reward-config", default=None, help="JSON with RewardWeights (weighted mode)")
    args = ap.parse_args()

    cfg = build_config(
        penalty=floats(args.penalty, 5), turn=floats(args.turn, 3), scoring=args.scoring,
        collab_w=floats(args.collab_w, 3) if args.collab_w else None, cdecay=args.cdecay, timesteps=args.timesteps,
        reward_mode=args.reward_mode,
        reward_weights=RewardWeights.load(args.reward_config) if args.reward_config else None,
        zero_profiles=args.zero_profiles, engine=args.engine,
        teammates=args.teammates.split(",") if args.teammates else None,
        deck=args.deck, extra_cards=args.extra_cards, history_fights=args.history_fights,
        pool_weights=floats(args.pool_weights, 3) if args.pool_weights else None,
        no_wait=args.no_wait, blind_teammates=args.blind_teammates,
        start_hp=percents(args.start_hp) if args.start_hp else None,
        team_penalty=floats(args.team_penalty, 2) if args.team_penalty else None,
        sort_teammates=args.sort_teammates, network=args.network,
        deck_presets=args.deck_presets.split(",") if args.deck_presets else None, pool_cards=args.pool_cards,
        card_effects=args.card_effects, enemy_statuses=args.enemy_statuses,
    )
    path = train(cfg, args.timesteps, args.out, args.n_envs, args.seed, args.subproc, args.resume)
    print("saved", path)


if __name__ == "__main__":   # needed on Windows for --subproc
    main()
