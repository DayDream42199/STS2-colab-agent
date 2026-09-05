"""bench.py -- combat difficulty measurement."""

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
MAX_TURNS = 60
DEFAULT_SEEDS = 40


def _applies_vulnerable(card) -> bool:
    """String-matched on purpose: Card has no structured 'what statuses do I apply' data, and adding..."""
    desc = card.current_description().lower()
    return "apply" in desc and "vulnerable" in desc


def _grants_block(card) -> bool:
    return "block" in card.current_description().lower()


def _incoming_damage(engine) -> int:
    """Rough estimate of damage aimed at the player next enemy phase."""
    total = 0
    for e in engine.enemies_alive():
        mv = e.current_move
        if mv and mv.damage:
            total += mv.damage + e.get_status(StatusType.STRENGTH)
    return total


def greedy_policy(engine, player):
    """Pick one card to play, or None to end the turn."""
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
    """A crude "how much do I want this card" score, in damage-equivalent units."""
    if card.card_type in (CardType.STATUS, CardType.CURSE):
        return -100.0
    v = float(card.val("damage") + card.val("block"))
    if card.card_type == CardType.POWER:
        v += 12.0
    if card.upgraded:
        v += 2.0
    return v


GAIN_PROMPTS = {"to_hand", "copy", "to_draw_top"}


def greedy_choice(engine, player, options, prompt, kind):
    """Answer CombatEngine.request_choice for the benchmark."""
    if kind in GAIN_PROMPTS:
        return max(options, key=_card_value)
    return player.rng.choice(options)


def maybe_use_potion(engine, player) -> bool:
    """Spend a potion when it's likely to matter."""
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
            return


DECK_TIERS = {
    1: dict(extra_cards=0,  upgrade_frac=0.00, relics=0, max_hp=80),
    2: dict(extra_cards=5,  upgrade_frac=0.15, relics=1, max_hp=80),
    3: dict(extra_cards=8,  upgrade_frac=0.25, relics=2, max_hp=80),
    4: dict(extra_cards=12, upgrade_frac=0.35, relics=3, max_hp=80),
    5: dict(extra_cards=16, upgrade_frac=0.45, relics=4, max_hp=80),
    6: dict(extra_cards=20, upgrade_frac=0.55, relics=5, max_hp=80),
}


def build_deck_for_tier(tier: int, rng: random.Random):
    """Starter deck plus `extra_cards` random pool cards, a fraction of the whole upgraded."""
    spec = DECK_TIERS[tier]
    deck = make_starter_deck()
    for _ in range(spec["extra_cards"]):
        deck.append(rng.choice(CARD_POOL_IRONCLAD)())
    for c in deck:
        if rng.random() < spec["upgrade_frac"]:
            c.upgrade()
    return deck


def run_encounter(make_enemies, seed, tier: int = 1):
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

from testing.play import region_of, tier_of, REGION_ORDER

ORDER = REGION_ORDER


def _measure(make_enemies, seeds, tier):
    """(win%, avg HP lost on wins, avg turns, timeouts) at one deck tier."""
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


def run_gauntlet_once(seed):
    """Drives the real play.run_gauntlet so the measured curve is the one players actually get..."""
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
    """OPT-IN."""
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
