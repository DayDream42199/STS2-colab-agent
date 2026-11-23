"""Reward experiments from the ColabReward spec.

    python experiments.py bc        # 1a. B vs C, series 1             (collaboration off)
    python experiments.py ad        # 1b. A vs D, series 2, best B, C  (collaboration off)
    python experiments.py e         # 1c. E = 5, 10, 20, series 3      (collaboration off)
    python experiments.py turn      # 1d. turn-cost shape, only if the best E >= 10
    python experiments.py collab    # 2.  collaborative scorings x weights, CDecay 0.5
    python experiments.py cdecay    # 3.  CDecay for the best 1-2 of stage 2
    python experiments.py all       # all in order, each stage starting from the best before it

Options:  --timesteps 1000000  --seeds 0,1,2  --episodes 500  --n-envs 8 --subproc  --dry-run  --engine real
Finished runs are skipped, so you can stop and continue. Results: runs/experiments/

Ranking. Stages 1a-1d: highest win rate > most ally HP left > fewest rounds. Stages 2-3:
settings whose score falls more than --score-gate below the stage 1 winner's go last (helping
must not cost the team); the rest by advantage point, then assist share. Two settings tie on a
number when they differ by less than the tie size or than the spread between their seeds.
"""
import argparse
import csv
import functools
import json
import os
import statistics

from train import build_config, train
from evaluate import evaluate_model

ROOT = "runs/experiments"

# ------------------------------------------------------------------ what to test (edit freely)
BC_SETS = [(45, 15, 25, 15), (45, 20, 20, 15), (45, 25, 15, 15), (45, 30, 10, 15), (45, 35, 5, 15)]  # A,B,C,D
AD_SETS = [(45, 15), (40, 20), (35, 25), (30, 30), (25, 35)]    # (A, D), with B, C from the best of "bc"
E_SETS = (5, 10, 20)
DEFAULT_E = 5
DEFAULT_TURN = (6, 10, 0.35)
TURN_SETS = [(4, 8, 0.35), (6, 10, 0.35), (8, 12, 0.35),       # move the range
             (7, 9, 0.35), (5, 11, 0.35),                        # narrower, wider
             (6, 10, 0.25), (6, 10, 0.50)]                       # sharper, gentler
TURN_MIN_E = 10       # below this the turn cost is too small for its shape to matter
COLLAB_OFF = ("baseline", (0, 0, 0))
COLLAB_SETS = [       # (scoring, (w_offense, w_defense, w_others)); each scoring's starting weights in the middle
    ("baseline", (3, 2, 0)), ("baseline", (7, 2, 0)), ("baseline", (15, 2, 0)),
    ("baseline", (7, 1, 0)), ("baseline", (7, 5, 0)),
    ("variant1", (0.1, 0.1, 0)), ("variant1", (0.2, 0.2, 0)), ("variant1", (0.4, 0.4, 0)),
    ("variant2", (1.5, 1.5, 0)), ("variant2", (3, 3, 0)), ("variant2", (6, 6, 0)),
    ("variant3", (0, 0, 1.5)), ("variant3", (0, 0, 3)), ("variant3", (0, 0, 6)),
    ("variant4", (3, 3, 3)),
]
COLLAB_CDECAY = 0.5
CDECAYS = (0.0, 0.25, 0.5, 0.75, 1.0)
OUTCOME_STAGES = ("bc", "ad", "e", "turn")
STAGES = OUTCOME_STAGES + ("collab", "cdecay")
SPREAD_KEYS = ("win", "ally_hp_frac", "score", "advantage")


def fmt(xs):
    return "_".join(f"{x:g}" for x in xs)


# ------------------------------------------------------------------ ranking
def _tied(a, b, key, tie):
    """Equal on `key`: closer than `tie`, or than the larger spread between either one's seeds."""
    return abs(a[key] - b[key]) <= max(tie, a.get(key + "_sd", 0.0), b.get(key + "_sd", 0.0))


def by_outcome(tie):
    """Stage 1: highest win rate > most ally HP left > fewest rounds."""
    def cmp(x, y):
        a, b = x["metrics"], y["metrics"]
        for key in ("win", "ally_hp_frac"):
            if not _tied(a, b, key, tie):
                return -1 if a[key] > b[key] else 1
        return -1 if a["rounds"] < b["rounds"] else 1 if a["rounds"] > b["rounds"] else 0
    return functools.cmp_to_key(cmp)


def by_advantage(adv_tie):
    """Stages 2-3: highest advantage point > highest assist share."""
    def cmp(x, y):
        a, b = x["metrics"], y["metrics"]
        if not _tied(a, b, "advantage", adv_tie):
            return -1 if a["advantage"] > b["advantage"] else 1
        return -1 if a["assist_share"] > b["assist_share"] else 1 if a["assist_share"] < b["assist_share"] else 0
    return functools.cmp_to_key(cmp)


def rank(stage, results, args, best):
    if stage in OUTCOME_STAGES:
        return sorted(results, key=by_outcome(args.tie))
    floor = best.get("floor_score")
    ok = [r for r in results if floor is None or r["metrics"]["score"] >= floor - args.score_gate]
    rest = [r for r in results if r not in ok]
    key = by_advantage(args.adv_tie)
    return sorted(ok, key=key) + sorted(rest, key=key)


# ------------------------------------------------------------------ running
def _index():
    """Finished runs by their exact settings, so a setting met again in a later stage
    (the winner carried forward, CDecay 0.5) is not trained twice."""
    path = os.path.join(ROOT, "index.json")
    return json.load(open(path)) if os.path.exists(path) else {}


def _run_key(params, seed, args):
    plain = {k: list(v) if isinstance(v, tuple) else v for k, v in params.items()}
    return json.dumps(dict(plain, seed=seed, timesteps=args.timesteps, episodes=args.episodes), sort_keys=True)


def run_one(stage, name, params, args):
    """Train (one model per seed) and evaluate; returns the metrics averaged over seeds, with
    the spread between seeds as <key>_sd. Skips finished runs, in this stage or any other."""
    metrics = []
    for seed in args.seeds:
        out = os.path.join(ROOT, stage, name, f"seed{seed}")
        result_path = os.path.join(out, "result.json")
        earlier = _index().get(_run_key(params, seed, args))
        found = next((p for p in (result_path, earlier) if p and os.path.exists(p)), None)
        if found:
            with open(found) as f:
                metrics.append(json.load(f))
            continue
        cfg = build_config(penalty=params["penalty"], turn=params["turn"], scoring=params["scoring"],
                           collab_w=params["collab_w"], cdecay=params["cdecay"], timesteps=args.timesteps,
                           engine=args.engine)
        print(f"\n=== {stage} / {name} / seed {seed}: training {args.timesteps:,} steps", flush=True)
        model = train(cfg, args.timesteps, out, args.n_envs, seed, args.subproc, verbose=0)
        m = evaluate_model(model, episodes=args.episodes)
        with open(result_path, "w") as f:
            json.dump(m, f, indent=2)
        index = _index()
        index[_run_key(params, seed, args)] = result_path
        with open(os.path.join(ROOT, "index.json"), "w") as f:
            json.dump(index, f, indent=1)
        metrics.append(m)
    keys = [k for k, v in metrics[0].items() if isinstance(v, (int, float))]
    avg = {k: sum(m[k] for m in metrics) / len(metrics) for k in keys}
    for k in SPREAD_KEYS:
        avg[k + "_sd"] = statistics.pstdev(m[k] for m in metrics) if len(metrics) > 1 else 0.0
    return avg


def stage_runs(stage, best):
    penalty = tuple(best.get("penalty", BC_SETS[0] + (DEFAULT_E,)))
    base = dict(penalty=penalty, turn=tuple(best.get("turn", DEFAULT_TURN)),
                scoring=COLLAB_OFF[0], collab_w=COLLAB_OFF[1], cdecay=0.0)
    if stage == "bc":
        return [(f"pen_{fmt(p + (DEFAULT_E,))}", dict(base, penalty=p + (DEFAULT_E,), turn=DEFAULT_TURN))
                for p in BC_SETS]
    if stage == "ad":
        _, B, C, _, E = penalty
        return [(f"pen_{fmt((A, B, C, D, E))}", dict(base, penalty=(A, B, C, D, E))) for A, D in AD_SETS]
    if stage == "e":
        return [(f"pen_{fmt(penalty[:4] + (e,))}", dict(base, penalty=penalty[:4] + (e,))) for e in E_SETS]
    if stage == "turn":
        return [(f"turn_{fmt(t)}", dict(base, turn=t)) for t in TURN_SETS]
    if stage == "collab":
        cdecay = best.get("cdecay_fixed", COLLAB_CDECAY)
        return [(f"{s}_w{fmt(w)}", dict(base, scoring=s, collab_w=w, cdecay=cdecay)) for s, w in COLLAB_SETS]
    if stage == "cdecay":
        tops = best.get("top_collab") or [[best.get("scoring", "baseline"), best.get("collab_w", [7, 2, 0])]]
        return [(f"{s}_w{fmt(w)}_cdecay_{d:g}", dict(base, scoring=s, collab_w=tuple(w), cdecay=d))
                for s, w in tops[:2] for d in CDECAYS]
    raise ValueError(stage)


def load_best():
    path = os.path.join(ROOT, "best.json")
    return json.load(open(path)) if os.path.exists(path) else {}


def save_best(best):
    os.makedirs(ROOT, exist_ok=True)
    with open(os.path.join(ROOT, "best.json"), "w") as f:
        json.dump(best, f, indent=2)


def run_stage(stage, args):
    best = load_best()
    if args.cdecay_fixed is not None:
        best["cdecay_fixed"] = args.cdecay_fixed
    best_e = best.get("penalty", BC_SETS[0] + (DEFAULT_E,))[4]
    if stage == "turn" and best_e < TURN_MIN_E:
        print(f"\n##### stage 'turn' skipped: the best E is {best_e:g}, below {TURN_MIN_E} - "
              f"too small for the shape to matter")
        return
    runs = stage_runs(stage, best)
    print(f"\n##### stage '{stage}': {len(runs)} settings x {len(args.seeds)} seed(s)")
    if args.dry_run:
        for name, p in runs:
            print(f"  {name:32s} {p}")
        return
    results = [dict(name=name, params=p, metrics=run_one(stage, name, p, args)) for name, p in runs]
    ranked = rank(stage, results, args, best)

    # g_n = Adv(this agent) - Adv(the best baseline agent of this stage), when there is one
    base_adv = next((r["metrics"]["advantage"] for r in ranked if r["params"]["scoring"] == "baseline"
                     and any(r["params"]["collab_w"])), None)
    print(f"\n{'rank':4s} {'setting':32s} {'win':>5s} {'ally_hp':>8s} {'turns':>6s} {'score':>6s} "
          f"{'advantage':>10s} {'g_n':>7s} {'assist':>7s}")
    for i, r in enumerate(ranked, 1):
        m = r["metrics"]
        g = f"{m['advantage'] - base_adv:+7.2f}" if base_adv is not None else f"{'-':>7s}"
        print(f"{i:<4d} {r['name']:32s} {m['win']:5.2f} {m['ally_hp_frac']:8.2f} {m['rounds']:6.1f} "
              f"{m['score']:6.1f} {m['advantage']:+10.2f} {g} {m['assist_share']:7.2f}")

    with open(os.path.join(ROOT, f"{stage}_results.csv"), "w", newline="") as f:
        w = csv.writer(f)
        keys = list(ranked[0]["metrics"])
        w.writerow(["rank", "setting"] + list(ranked[0]["params"]) + keys)
        for i, r in enumerate(ranked, 1):
            w.writerow([i, r["name"]] + list(r["params"].values()) + [r["metrics"][k] for k in keys])

    top = ranked[0]["params"]
    if stage in ("bc", "ad", "e"):
        best["penalty"] = list(top["penalty"])
    elif stage == "turn":
        best["turn"] = list(top["turn"])
    elif stage == "collab":
        best["scoring"], best["collab_w"] = top["scoring"], list(top["collab_w"])
        best["top_collab"] = [[r["params"]["scoring"], list(r["params"]["collab_w"])] for r in ranked[:2]]
    else:
        best["cdecay"] = top["cdecay"]
    if stage in OUTCOME_STAGES:
        best["floor_score"] = ranked[0]["metrics"]["score"]      # stage 2's gate: helping must not cost this
    best[f"top3_{stage}"] = [r["name"] for r in ranked[:3]]
    save_best(best)
    print(f"best {stage}: {ranked[0]['name']}   (saved in {ROOT}/best.json)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=list(STAGES) + ["all"])
    ap.add_argument("--timesteps", type=int, default=1_000_000)
    ap.add_argument("--seeds", default="0,1,2", help="comma-separated, e.g. 0,1,2")
    ap.add_argument("--episodes", type=int, default=500, help="evaluation fights per run (each played twice)")
    ap.add_argument("--n-envs", type=int, default=8)
    ap.add_argument("--subproc", action="store_true")
    ap.add_argument("--tie", type=float, default=0.02, help="win / HP differences below this count as a tie")
    ap.add_argument("--adv-tie", type=float, default=2.0,
                    help="advantage differences (score points) that tie: about its noise at 500 fights per side")
    ap.add_argument("--score-gate", type=float, default=2.0,
                    help="stages 2-3: score points a setting may fall below the stage 1 winner and still rank")
    ap.add_argument("--cdecay-fixed", type=float, default=None,
                    help=f"CDecay for the collab stage (default {COLLAB_CDECAY})")
    ap.add_argument("--dry-run", action="store_true", help="only list the settings")
    ap.add_argument("--engine", default="mock", choices=["mock", "real"],
                    help="real: 2nd_model's engine; its runs go to runs/experiments_real/")
    args = ap.parse_args()
    args.seeds = [int(s) for s in args.seeds.split(",")]
    global ROOT
    if args.engine == "real":
        ROOT = "runs/experiments_real"          # its own best.json and results: never mixed with the mock's

    for stage in (STAGES if args.stage == "all" else [args.stage]):
        run_stage(stage, args)


if __name__ == "__main__":   # needed on Windows for --subproc
    main()
