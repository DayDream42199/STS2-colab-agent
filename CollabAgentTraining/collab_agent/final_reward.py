"""Final_reward_norm (ColabReward spec), paid as the change each step.

    Score_t = 100 - General_penalty_t
    r_t     = 1/100 * (Score_t - Score_(t-1))
            + 1/50  * (Collab_t - Collab_(t-1)) * (1 - min(CTime / DTime, 1) * CDecay)

Score is read every time the agent is asked to act and once more when the
fight ends. Over a fight the general part adds up to (Score_final -
Score_start) / 100, however many steps it took, so a long fight is never paid
more for its length. A is charged only on the read where the fight is lost.
The collaborative part is given on the step where each event happens.
"""
import math
from dataclasses import dataclass, field


# ------------------------------------------------------------------ settings
@dataclass
class PenaltyWeights:
    A: float = 45.0   # losing the fight (charged only once it is lost)
    B: float = 15.0   # allies' HP pool lost
    C: float = 25.0   # allies knocked out
    D: float = 15.0   # enemy HP left            A + B + C + D = 100
    E: float = 5.0    # turn count, on top of the 100
    a: float = 6.0    # turn cost rises fastest between a and b
    b: float = 10.0
    c: float = 0.35   # how gentle the rise is: bigger c = gentler
    # Optional, both or neither: teammates on their own weights. B and C are then the agent's own HP and
    # knockout, B_team and C_team the teammates' (--team-penalty). None: B and C cover the whole team.
    B_team: float = None
    C_team: float = None

    def check(self):
        """A + B + C + D (+ B_team + C_team) = 100, and E small enough that any win beats any loss
        with up to 4 players (E < A + C / 4; with teammates apart, E < A + min(C, C_team / 3))."""
        split = self.B_team is not None
        if split != (self.C_team is not None):
            raise ValueError("B_team and C_team go together: give both or neither")
        total = self.A + self.B + self.C + self.D + (self.B_team + self.C_team if split else 0)
        if abs(total - 100) > 1e-9:
            raise ValueError(f"A + B + C + D{' + B_team + C_team' if split else ''} must be 100, got {total:g}")
        floor = self.A + (min(self.C, self.C_team / 3) if split else self.C / 4)
        if not self.E < floor:
            raise ValueError(f"E = {self.E:g} lets a slow win score below a quick loss: keep it under {floor:g}")
        return self


@dataclass
class CollabSettings:
    scoring: str = "baseline"     # which f_n trains the agent: see SCORINGS
    w_offense: float = 7.0
    w_defense: float = 2.0
    w_others: float = 0.0
    cdecay: float = 0.5           # 0, 0.25, 0.5, 0.75, 1.0
    decay_fraction: float = 0.5   # DTime = decay_fraction * total training steps


@dataclass
class FinalRewardConfig:
    penalty: PenaltyWeights = field(default_factory=PenaltyWeights)
    collab: CollabSettings = field(default_factory=CollabSettings)
    total_timesteps: int = 2_000_000   # set by train.py


# ------------------------------------------------------------------ general penalty
def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def turn_cost(turn_count, a, b, c):
    """[σ((t − m)/s) − σ(−m/s)] / [1 − σ(−m/s)],  m = (a + b)/2,  s = c(b − a).  0 at t = 0, → 1."""
    s = c * (b - a)
    if s == 0:
        raise ValueError(f"turn cost needs s = c*(b - a) != 0 (a={a}, b={b}, c={c})")
    m = (a + b) / 2
    low = sigmoid(-m / s)
    return (sigmoid((turn_count - m) / s) - low) / (1 - low)


def general_penalty(fight, w: PenaltyWeights):
    """fight: lost, ally_hp, ally_max_hp, allies_alive, allies, enemy_hp, enemy_max_hp, turns; with B_team and
    C_team also self_hp, self_max_hp, self_alive, mate_hp, mate_max_hp, mates_alive, mates.
    'Allies' is the whole team, the agent included. Works mid-fight: A only once the fight is lost.
    Each fraction is kept to [0, 1], so A + B + C + D = 100 holds whatever the engine reports (an
    enemy past the HP it came in with would otherwise run D past its weight)."""
    frac = lambda x: min(1.0, max(0.0, x))
    if w.B_team is None:
        pen_b = w.B * frac(1 - fight["ally_hp"] / fight["ally_max_hp"]) if fight["ally_max_hp"] > 0 else w.B
        pen_c = w.C * frac(1 - fight["allies_alive"] / fight["allies"]) if fight["allies"] > 0 else w.C
    else:
        pen_b = w.B * frac(1 - fight["self_hp"] / fight["self_max_hp"])
        pen_c = w.C * (0 if fight["self_alive"] else 1)
        if fight["mates"] > 0:
            pen_b += w.B_team * frac(1 - fight["mate_hp"] / fight["mate_max_hp"])
            pen_c += w.C_team * frac(1 - fight["mates_alive"] / fight["mates"])
    parts = {
        "pen_A": w.A * (1 if fight["lost"] else 0),
        "pen_B": pen_b,
        "pen_C": pen_c,
        "pen_D": w.D * frac(fight["enemy_hp"] / fight["enemy_max_hp"]) if fight["enemy_max_hp"] > 0 else 0.0,
        "pen_E": w.E * turn_cost(fight["turns"], w.a, w.b, w.c),
    }
    return sum(parts.values()), parts


def score(fight, w: PenaltyWeights):
    return 100 - general_penalty(fight, w)[0]


# ------------------------------------------------------------------ collaborative scoring f_n
# Every f_n takes this step's stats (engine.new_stats) and ctx: profiles (seat -> the
# teammate's profile now), teammates (their seats), enemy_pool and ally_pool (max HP).

def f_baseline(stats, ctx):
    """f_0_baseline: counts of the agent's debuffs + Block given, weighted by the ally's Aggression."""
    seats, profiles = ctx["teammates"], ctx["profiles"]
    n = len(seats)
    block_part = 0.0
    for i in seats:
        p = profiles.get(i)
        if p is not None and n > 0:
            block_part += p["A"] * min(p["c_A"] + 0.5, 1.0) * stats["block_to_ally"][i]
    return {
        "offense": 0.1 * stats["vuln_applied"],
        "defense": (0.2 * block_part / n if n > 0 else 0.0) + 0.1 * stats["weak_applied"],
        "others": 0.0,
    }


def f_variant1(stats, ctx):
    """f_0_variant1: bonus enemy HP teammates removed because of the agent's Vulnerable, and
    teammate HP saved by its Weak and its Block, in % of the enemy / ally HP pool."""
    return {
        "offense": 100 * stats["bonus_damage"] / ctx["enemy_pool"] if ctx["enemy_pool"] > 0 else 0.0,
        "defense": 100 * stats["hp_saved"] / ctx["ally_pool"] if ctx["ally_pool"] > 0 else 0.0,
        "others": 0.0,
    }


def f_variant2(stats, ctx):
    """f_0_variant2 (cash-in counts): help counts only when a teammate's play made it count.
    Teammates' hits on the agent's Vulnerable; enemy hits where the agent's Weak still saved HP;
    enemy hits the agent's Block soaked up. Shared stacks count by the agent's share."""
    return {
        "offense": 0.1 * stats["vuln_cashed"],
        "defense": 0.1 * stats["weak_cashed"] + 0.1 * stats["block_cashed"],
        "others": 0.0,
    }


def f_variant3(stats, ctx):
    """f_0_variant3 (complement): covering the side of the game the teammates leave open
    (see complement(); the env adds it to the stats at each round end)."""
    return {"offense": 0.0, "defense": 0.0, "others": stats["complement"]}


def f_variant4(stats, ctx):
    """f_0_variant4: variant2's offense and defense with variant3's complement."""
    return dict(f_variant2(stats, ctx), others=stats["complement"])


SCORINGS = {"baseline": f_baseline, "variant1": f_variant1, "variant2": f_variant2,
            "variant3": f_variant3, "variant4": f_variant4}   # add f_0_variantn here
BASELINE = "baseline"
# starting weights (w_offense, w_defense, w_others), set from 60 fights each of a random agent
# and the Cheese bot: a fight's collaborative part (f / 50) then comes to about 0.03 - 0.06,
# below what separates a good win from a poor one
DEFAULT_WEIGHTS = {"baseline": (7, 2, 0), "variant1": (0.2, 0.2, 0), "variant2": (3, 3, 0),
                   "variant3": (0, 0, 3), "variant4": (3, 3, 3)}


def complement(evidence, profiles, seats):
    """f_0_variant3's term for one round. For each teammate: the side of the game they leave
    open times what the agent did on that side, from the agent's own evidence e and weight w
    (analyzer.turn_evidence). A and S both ways (Block next to an attacker, attack next to a
    blocker; now-cards next to a scaler, Powers next to a now-player); T one way only (team
    cards when the teammate looks after only themself). Block with nothing coming, or playing
    nothing, gives e = 0 or w = 0, so it cannot be farmed."""
    total = 0.0
    for i in seats:
        p = profiles.get(i)
        if p is None:
            continue
        k = {t: min(p["c_" + t] + 0.5, 1.0) for t in "AST"}
        total += -p["A"] * k["A"] * evidence["e_A"] * evidence["w_A"]
        total += -p["S"] * k["S"] * evidence["e_S"] * evidence["w_S"]
        total += max(0.0, -p["T"]) * k["T"] * max(0.0, evidence["e_T"]) * evidence["w_T"]
    return total


def weighted(parts, c: CollabSettings):
    return weighted_by(parts, (c.w_offense, c.w_defense, c.w_others))


def weighted_by(parts, w):
    """parts weighted by (w_offense, w_defense, w_others)."""
    return w[0] * parts["offense"] + w[1] * parts["defense"] + w[2] * parts["others"]


def decay_factor(ctime, c: CollabSettings, total_timesteps):
    dtime = c.decay_fraction * total_timesteps
    return 1.0 - min(ctime / dtime, 1.0) * c.cdecay if dtime > 0 else 1.0 - c.cdecay


def advantage_point(scores_true, scores_swapped):
    """Adv = mean Score_final with the true teammate profiles - mean with swapped ones (in the
    agent's input only; evaluate.py plays the same fights both ways). Above 0: the agent plays
    better when it knows who its teammates really are. g_n = Adv(f_n agent) - Adv(baseline agent)."""
    if not scores_true or not scores_swapped:
        return 0.0
    return sum(scores_true) / len(scores_true) - sum(scores_swapped) / len(scores_swapped)
