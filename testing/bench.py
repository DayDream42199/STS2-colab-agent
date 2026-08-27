"""
bench.py -- combat difficulty measurement.

Part A measures COMBAT: every encounter run independently, no rewards, no
carry-over. That is the number to trust, and it is the default output.
Each fight is measured twice -- once on a fixed starter deck (one yardstick
for everything, so it shows how the CONTENT scales) and once on a deck
sized to where the fight sits in a run (what a player EXPERIENCES).

Part B measures the 6-fight gauntlet, which is a different thing and a
weaker one. It bundles reward luck into the result: adding two items to
the reward pools once moved its clear rate from 6/40 to 9/40 purely by
reshuffling later draws, and three values recorded across sessions (18%,
15%, 22%) were one result inside the noise. Reward pacing is also this
replica's own invention rather than the game's. So Part B is opt-in and
its number should never be quoted as a balance finding.

Run: python bench.py                 (Part A, default seeds)
     python bench.py 100             (more seeds = tighter, slower)
     python bench.py 40 --gauntlet   (also run the noisy Part B)

WHY THIS EXISTS
---------------
The first attempt at this measured only "did the whole gauntlet get
cleared", with a policy that skipped every card reward and picked cards by
cheapest cost. That policy loses to almost everything, so it returned
0/15 both before AND after a change that provably altered enemy behaviour
-- a floor effect that made the benchmark blind. Two lessons are baked in
here: measure PER-ENCOUNTER (so one brutal fight can't mask everything
behind it), and use a policy good enough that results aren't pinned to the
floor.

WHAT THE NUMBERS ARE AND AREN'T
-------------------------------
`greedy_policy` below is a scripted heuristic, not a good player. It never
plans ahead, never builds toward a deck archetype, and evaluates cards by
string-matching their description text. So treat output as a RELATIVE
signal -- "Vantom kills 90% of runs while Byrdonis kills 10%" is a real
finding; "encounter X has a 60% win rate therefore it is fairly tuned" is
not. Its other job is regression detection: re-run after any balance-
touching change and look for numbers that move when they shouldn't.

It cannot beat Act 2/3 bosses, and that is expected rather than a data
problem: every fight that sat near 0% on the top rung was re-checked with
an absurd loadout (250 HP, 6 energy, 40 upgraded cards, 11 relics) and all
13 became winnable, 12 of them at 100%. Nothing is ported unwinnable.

TWO STATISTICS TRAPS THIS HARNESS HAS ALREADY FALLEN INTO (task #36)
--------------------------------------------------------------------
1. MEDIAN over a bimodal group. Normals in a region split into trivial and
   real fights, so the median reports whichever cluster is bigger and reads
   flat while the mean descends. A "flat difficulty curve" was chased as a
   balance bug for a whole session; it was this. Group blocks now print
   mean AND median -- when they disagree, look at the distribution.
2. A SATURATED metric. Every Act 1 Overgrowth normal wins 40/40, so win
   rate cannot tell a Twig Slime from a Mawler. Average HP lost can (0 vs
   29) and stays informative where win rate is pinned at the ceiling.
"""

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


import sys
import io
import random
import itertools
import contextlib
from statistics import mean

from game_engine.entities import Player, seed_content
from game_engine.cards import make_starter_deck, CARD_POOL_IRONCLAD, CardType, TargetMode
from game_engine.combat import CombatEngine
from game_engine.relics import BURNING_BLOOD, RELIC_POOL_IRONCLAD
from game_engine.statuses import StatusType
import testing.play as play
MAX_TURNS = 60          # safety cap; a fight hitting this is itself a finding
DEFAULT_SEEDS = 40


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

def _applies_vulnerable(card) -> bool:
    """String-matched on purpose: Card has no structured 'what statuses do
    I apply' data, and adding one just for the benchmark would put test-only
    fields on a core model. Requires BOTH 'apply' and 'vulnerable' so cards
    that merely READ Vulnerable (Bully "for each Vulnerable on the enemy",
    Molten Fist "double the enemy's Vulnerable") don't match."""
    desc = card.current_description().lower()
    return "apply" in desc and "vulnerable" in desc


def _grants_block(card) -> bool:
    return "block" in card.current_description().lower()


def _incoming_damage(engine) -> int:
    """Rough estimate of damage aimed at the player next enemy phase.
    Move.damage is BASE PER-HIT damage, so multi-hit moves (Peck = 3 damage
    x3) under-report badly. Deliberately kept rough -- it only has to be
    good enough to decide 'block or attack', and a smarter estimate would
    mean teaching the benchmark every move's hit count."""
    total = 0
    for e in engine.enemies_alive():
        mv = e.current_move
        if mv and mv.damage:
            total += mv.damage + e.get_status(StatusType.STRENGTH)
    return total


def greedy_policy(engine, player):
    """Pick one card to play, or None to end the turn.

    Priority, in order:
      1. Powers -- they compound, so earlier is strictly better
      2. Apply Vulnerable if the focus target lacks it (this is the whole
         reason the old cheapest-first policy was so weak: it never set up
         the 1.5x multiplier before spending damage into it)
      3. Block, but only when actually threatened
      4. Biggest attack available
    """
    alive = engine.enemies_alive()
    if not alive:
        return None, None
    playable = [c for c in engine.playable_cards(player)
                if not (c.current_cost(player) == "X" and player.energy <= 0)]
    if not playable:
        return None, None

    focus = min(alive, key=lambda e: e.hp)

    powers = [c for c in playable if c.card_type == CardType.POWER]
    if powers:
        return powers[0], focus

    if focus.get_status(StatusType.VULNERABLE) == 0:
        setup = [c for c in playable if _applies_vulnerable(c)]
        if setup:
            return setup[0], focus

    incoming = _incoming_damage(engine)
    if incoming > player.block and player.hp <= incoming * 2:
        blocks = [c for c in playable
                  if c.card_type == CardType.SKILL and _grants_block(c)]
        if blocks:
            return max(blocks, key=lambda c: c.val("block")), focus

    attacks = [c for c in playable if c.card_type == CardType.ATTACK]
    if attacks:
        return max(attacks, key=lambda c: c.val("damage")), focus

    return playable[0], focus


def _card_value(card) -> float:
    """A crude "how much do I want this card" score, in damage-equivalent
    units. Same spirit as greedy_policy: good enough to rank, not a model."""
    if card.card_type in (CardType.STATUS, CardType.CURSE):
        return -100.0            # always the first thing to throw away
    v = float(card.val("damage") + card.val("block"))
    if card.card_type == CardType.POWER:
        v += 12.0                # powers compound, so they beat a one-shot
    if card.upgraded:
        v += 2.0
    return v


# Prompts that ADD a card to your side: tutors (Wish, Seeker Strike,
# Discovery, Abundance, Neow's Fury, Stratagem), Dual Wield's copy, and
# Headbutt recovering from the discard pile. These are the only prompts
# where being greedy measurably helps -- see greedy_choice.
GAIN_PROMPTS = {"to_hand", "copy", "to_draw_top"}


def greedy_choice(engine, player, options, prompt, kind):
    """Answer CombatEngine.request_choice for the benchmark.

    Greedy ONLY on gain prompts; everything else defers to random. That is
    an empirical result, not a preference. Measured over 1920 runs per arm
    (160 seeds x 12 non-saturated encounters, decks built around the choice
    cards):

        random, i.e. no resolver          50.21%
        greedy on GAIN prompts only       52.45%   (+2.24)
        greedy on EVERY prompt            49.48%   (-0.73)

    Being greedy everywhere is WORSE THAN RANDOM. The gain from tutoring
    well is real, and the shed-side prompts (exhaust / transform / stash)
    plus `upgrade` more than cancel it.

    Two caveats worth keeping straight:

    * This is tuned to THIS BENCHMARK'S POLICY, not to correct play. A
      human would obviously upgrade their biggest card, but greedy `upgrade`
      measured slightly negative here because greedy_policy cannot exploit
      it. play.py asks the human instead, which is the right answer there.
    * The first version of this function was greedy everywhere and cost 4pp.
      Chasing that down found a real bug rather than just a bad weight:
      Headbutt and Thinking Ahead had both been filed under `to_draw_top`,
      but Headbutt RECOVERS a card from the discard pile (you want the best)
      while Thinking Ahead SHEDS one from your hand (you want the worst).
      One kind, two opposite preferences, so a resolver had to be wrong for
      one of them. Thinking Ahead is now `stash`."""
    if kind in GAIN_PROMPTS:
        return max(options, key=_card_value)
    return player.rng.choice(options)


def maybe_use_potion(engine, player) -> bool:
    """Spend a potion when it's likely to matter. Without this the gauntlet
    bot happily collected potions and died holding them, which understated
    how far a run can actually get. Fires when hurt, when the belt is full
    (so rewards aren't wasted), or against a boss-sized HP pool."""
    if not player.potions:
        return False
    alive = engine.enemies_alive()
    if not alive:
        return False
    hurt = player.hp < player.max_hp * 0.5
    belt_full = len(player.potions) >= player.potion_slots
    big_fight = max(e.max_hp for e in alive) > 100
    if not (hurt or belt_full or big_fight):
        return False
    potion = player.potions[0]
    target = min(alive, key=lambda e: e.hp) if potion.target == "enemy" else None
    return engine.use_potion(player, potion, target=target)


def take_player_turn(engine, player):
    """Play cards until the policy declines or a play fails."""
    guard = 0
    while not engine.is_over and guard < 50:
        guard += 1
        card, focus = greedy_policy(engine, player)
        if card is None:
            return
        target = focus if card.target == TargetMode.SINGLE_ENEMY else None
        ally = engine.other_player(player) if card.target == TargetMode.ALLY else None
        if not engine.play_card(player, card, target=target, ally_target=ally):
            return   # refused play -> stop, never spin on it


# ---------------------------------------------------------------------------
# Part A -- per-encounter lethality, fixed starter deck
# ---------------------------------------------------------------------------

# How strong a deck the measurement gives the player, as a RUN-PROGRESS
# ladder. These are INVENTED baselines -- the real game has no such table --
# but measuring an Act 3 boss with a 10-card starter deck tells you nothing
# about that boss, only that a starting deck is not an Act 3 deck. Kept
# deliberately crude: extra pool cards, a share upgraded, and extra relics.
#
# Six rungs rather than three because deck growth does not step once per
# act. Keying this on the act alone was an outright measurement bug (see
# DECK_TIER_FOR): it fought Act 1 BOSSES with the Act 1 starter deck, which
# reported all three as 0% unwinnable when they are simply never fought on
# 10 cards. A player reaching them has ~8 fights of rewards behind them.
DECK_TIERS = {
    1: dict(extra_cards=0,  upgrade_frac=0.00, relics=0, max_hp=80),
    2: dict(extra_cards=5,  upgrade_frac=0.15, relics=1, max_hp=80),
    3: dict(extra_cards=8,  upgrade_frac=0.25, relics=2, max_hp=80),
    4: dict(extra_cards=12, upgrade_frac=0.35, relics=3, max_hp=80),
    5: dict(extra_cards=16, upgrade_frac=0.45, relics=4, max_hp=80),
    6: dict(extra_cards=20, upgrade_frac=0.55, relics=5, max_hp=80),
}


def build_deck_for_tier(tier: int, rng: random.Random):
    """Starter deck plus `extra_cards` random pool cards, a fraction of the
    whole upgraded. Uses the passed rng so a seed reproduces the deck."""
    spec = DECK_TIERS[tier]
    deck = make_starter_deck()
    for _ in range(spec["extra_cards"]):
        deck.append(rng.choice(CARD_POOL_IRONCLAD)())
    for c in deck:
        if rng.random() < spec["upgrade_frac"]:
            c.upgrade()
    return deck


def run_encounter(make_enemies, seed, tier: int = 1):
    # Two seedings, because there are two independent streams: the global
    # module (play.py's reward draws) and the content rng (the HP a factory
    # rolls). Enemy HP used to come off the global module, so `random.seed`
    # alone covered it; it now has its own stream and needs its own call, or
    # every measured fight would face a differently-sized enemy.
    random.seed(seed)
    seed_content(seed)
    rng = random.Random(seed)
    spec = DECK_TIERS[tier]
    p = Player("Ironclad", max_hp=spec["max_hp"], max_energy=3,
                deck=build_deck_for_tier(tier, rng))
    p.add_relic(BURNING_BLOOD)
    for r in rng.sample(RELIC_POOL_IRONCLAD, spec["relics"]):
        p.add_relic(r)
    enemies = make_enemies()
    engine = CombatEngine([p], enemies, seed=seed, scale_enemies=False)
    engine.choice_resolver = greedy_choice
    engine.start_player_turn()
    turns = 0
    while not engine.is_over and turns < MAX_TURNS:
        turns += 1
        take_player_turn(engine, p)
        if engine.is_over:
            break
        engine.end_player_turn()
        if engine.is_over:
            break
        engine.run_enemy_turn()
        if engine.is_over:
            break
        engine.start_player_turn()
    timed_out = not engine.is_over
    won = engine.is_over and engine.victory
    return won, timed_out, turns, max(0, p.hp)


# Which rung of the ladder each encounter is measured on, by (region, tier).
# Within an act you clear normals first, then an elite, then the boss, so
# the deck is bigger at each step -- an Act 1 boss is an END-of-act-1 fight,
# not a starting-deck fight. Rungs deliberately overlap across the act
# boundary (an act 1 boss and an act 2 normal are minutes apart in a run).
DECK_TIER_FOR = {
    ("Act 1  Overgrowth", "normal"): 1,
    ("Act 1  Overgrowth", "elite"):  2,
    ("Act 1  Overgrowth", "boss"):   3,
    ("Act 1  Underdocks", "normal"): 1,
    ("Act 1  Underdocks", "elite"):  2,
    ("Act 1  Underdocks", "boss"):   3,
    ("Act 2  Hive", "normal"):       3,
    ("Act 2  Hive", "elite"):        4,
    ("Act 2  Hive", "boss"):         5,
    ("Act 3  Glory", "normal"):      5,
    ("Act 3  Glory", "elite"):       6,
    ("Act 3  Glory", "boss"):        6,
    ("Event-only", "normal"):        3,
}

# region_of/tier_of now live in play.py, next to the ENCOUNTERS table they
# classify, so the interactive encounter menu can group by them too. The
# dependency can only run this way round: bench imports play.
from testing.play import region_of, tier_of, REGION_ORDER   # noqa: E402

ORDER = REGION_ORDER


def _measure(make_enemies, seeds, tier):
    """(win%, avg HP lost on wins, avg turns, timeouts) at one deck tier.

    HP lost is averaged over WINS ONLY. Including losses would score every
    death as "80 lost" and collapse the metric back into the win rate --
    the exact redundancy it exists to avoid."""
    res = [run_encounter(make_enemies, s, tier) for s in range(seeds)]
    wins = [r for r in res if r[0]]
    hp_lost = mean(DECK_TIERS[tier]["max_hp"] - r[3] for r in wins) if wins else None
    return (100.0 * len(wins) / len(res), hp_lost,
            mean(r[2] for r in res), sum(1 for r in res if r[1]), len(wins), len(res))


def part_a(seeds):
    print("=" * 78)
    print("PER-ENCOUNTER LETHALITY  (80 HP Ironclad, no rewards, no carry-over)")
    print("=" * 78)
    print("Each fight is an independent seeded run, measured TWICE:")
    print("  fixed  -- always the 10-card starter deck. Same yardstick for")
    print("            every fight, so it measures how the CONTENT scales.")
    print("  ladder -- a deck sized to where the fight sits in a run (see")
    print("            DECK_TIERS/DECK_TIER_FOR, both invented). Measures")
    print("            what a player plausibly EXPERIENCES there.")
    print()
    for t, spec in sorted(DECK_TIERS.items()):
        print(f"   rung {t}: +{spec['extra_cards']:>2} pool cards, "
              f"{int(spec['upgrade_frac']*100):>2}% upgraded, {spec['relics']} extra relics")
    print()

    groups = {}
    rows = []
    for key, (name, make_enemies) in play.ENCOUNTERS.items():
        region = region_of(name)
        tier = tier_of(make_enemies)
        rung = DECK_TIER_FOR.get((region, tier), 1)
        fixed = _measure(make_enemies, seeds, 1)
        ladder = _measure(make_enemies, seeds, rung) if rung != 1 else fixed
        row = (ladder[0], name, fixed, ladder, rung)
        rows.append(row)
        groups.setdefault((region, tier), []).append(row)

    for region in ORDER:
        for tier in ("normal", "elite", "boss"):
            block = groups.get((region, tier))
            if not block:
                continue
            print(f"-- {region}  |  {tier}s " + "-" * (78 - 22 - len(region) - len(tier)))
            print(f"   {'encounter':<36} {'fixed':>13} {'ladder':>16} {'turns':>7}")
            for _, name, fixed, ladder, rung in sorted(block, key=lambda r: r[3][0]):
                flag = "  TIMEOUTS" if ladder[3] else ""
                fx = f"{fixed[0]:>4.0f}% {_hp(fixed[1]):>6}"
                ld = f"r{rung} {ladder[4]:>3}/{ladder[5]:<3}{ladder[0]:>4.0f}% {_hp(ladder[1]):>6}"
                print(f"   {name:<36} {fx} {ld} {ladder[2]:>6.1f}{flag}")
            _group_stats(block)
            print()

    print("=" * 78)
    print("DIFFICULTY CURVE  (normals only)")
    print("=" * 78)
    print("MEAN, not median. Normals inside a region are bimodal -- a cluster")
    print("of trivial fights and a cluster of real ones -- so the median just")
    print("reports whichever cluster holds more than half the encounters and")
    print("reads flat while the mean descends. That was the whole of task #36.")
    print()
    print(f"  {'region':<20} {'n':>3} {'fixed-deck win':>16} {'HP lost':>9} "
          f"{'ladder win':>12}")
    for region in ORDER:
        block = groups.get((region, "normal"))
        if not block:
            continue
        fw = mean(r[2][0] for r in block)
        lw = mean(r[3][0] for r in block)
        hp = [r[2][1] for r in block if r[2][1] is not None]
        bar = "#" * int(fw / 5)
        print(f"  {region:<20} {len(block):>3} {fw:>13.1f}%   {mean(hp):>7.1f} "
              f"{lw:>11.1f}%  {bar}")
    print()
    print("The fixed-deck column is the one that answers 'does the content")
    print("scale'. HP lost keeps working where win rate saturates at 100% and")
    print("stops distinguishing anything -- all of Act 1 is a 100% wall.")

    rows.sort(key=lambda r: r[3][0])
    print()
    print("deadliest encounters (on the run-progress ladder):")
    for _, name, fixed, ladder, rung in rows[:8]:
        print(f"   rung {rung}  {ladder[4]:>3}/{ladder[5]:<3} {ladder[0]:>4.0f}%  {name}")
    return rows


def _hp(v):
    return "-" if v is None else f"-{v:.0f}hp"


def _group_stats(block):
    for label, idx in (("fixed ", 2), ("ladder", 3)):
        wr = [r[idx][0] for r in block]
        print(f"   {'':<36} {label} mean {mean(wr):>5.1f}%  "
              f"median {sorted(wr)[len(wr)//2]:>5.1f}%")


# ---------------------------------------------------------------------------
# Part B -- gauntlet curve: how far does a run get, and where does it die?
# ---------------------------------------------------------------------------

def run_gauntlet_once(seed):
    """Drives the real play.run_gauntlet so the measured curve is the one
    players actually get (rewards, HP carry-over, revives included) rather
    than a reimplementation that could drift from it."""
    random.seed(seed)
    seed_content(seed)
    p = Player("Ironclad", max_hp=80, max_energy=3, deck=make_starter_deck())
    p.add_relic(BURNING_BLOOD)

    def auto_choose(engine, pending):
        return pending[0]

    def auto_act(engine, player, log_pos):
        if maybe_use_potion(engine, player):
            return False, log_pos
        card, focus = greedy_policy(engine, player)
        if card is None:
            return True, log_pos
        target = focus if card.target == TargetMode.SINGLE_ENEMY else None
        ally = engine.other_player(player) if card.target == TargetMode.ALLY else None
        if not engine.play_card(player, card, target=target, ally_target=ally):
            return True, log_pos
        return False, log_pos

    # Reward screens are the only thing still calling input(); "0" takes the
    # first offer every time. BOUNDED on purpose -- an unbounded generator
    # feeding a retry loop is exactly how an earlier stray test filled a disk
    # with a 29GB log. Past the cap this raises instead of spinning.
    answers = itertools.chain(["0"] * 500,
                              iter(lambda: (_ for _ in ()).throw(
                                  RuntimeError("benchmark hit an unexpected input() prompt")), None))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), \
         contextlib.suppress(SystemExit), \
         _patched(auto_choose, auto_act, answers):
        play.run_gauntlet([p])

    out = buf.getvalue()
    started = out.count("Encounter: ")
    cleared = "Gauntlet clear" in out
    return started, cleared, max(0, p.hp)


@contextlib.contextmanager
def _patched(auto_choose, auto_act, answers):
    from unittest.mock import patch
    with patch.object(play, "choose_active_character", auto_choose), \
         patch.object(play, "player_take_action", auto_act), \
         patch("builtins.input", lambda *_a, **_k: next(answers)):
        yield


def part_b(seeds):
    """OPT-IN. See the module docstring: this bundles reward luck into the
    result and its clear rate has never been stable enough to read as a
    balance signal."""
    print()
    print("=" * 78)
    print("GAUNTLET CURVE  (opt-in; measures reward luck as much as combat)")
    print("=" * 78)
    print("WARNING: adding items to the reward pools moves this number on its")
    print("own. Do not quote the clear rate as a balance result. See task #37.")
    print()
    names = [n for n, _ in play.GAUNTLET]
    results = [run_gauntlet_once(s) for s in range(seeds)]
    clears = sum(1 for r in results if r[1])

    print(f"{'fight':<26} {'reached':>8} {'died here':>10}")
    print("-" * 74)
    for i, name in enumerate(names, start=1):
        reached = sum(1 for started, _, _ in results if started >= i)
        died = sum(1 for started, cleared, _ in results
                   if started == i and not cleared)
        print(f"{i}. {name:<23} {reached:>8} {died:>10}")
    print("-" * 74)
    print(f"cleared all {len(names)} fights: {clears}/{len(results)} runs "
          f"({100.0*clears/len(results):.0f}%)")
    survivors = [hp for _, cleared, hp in results if cleared]
    if survivors:
        print(f"avg HP on clear: {mean(survivors):.1f}")
    return results


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    seeds = int(args[0]) if args else DEFAULT_SEEDS
    print(f"seeds per measurement: {seeds}\n")
    part_a(seeds)
    if "--gauntlet" in flags:
        part_b(seeds)
    else:
        print()
        print("(gauntlet curve skipped -- pass --gauntlet to run it; see #37)")
