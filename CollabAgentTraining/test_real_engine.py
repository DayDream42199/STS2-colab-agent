"""Checks for the real-engine adapter (collab_agent/real_engine.py):  python test_real_engine.py

Needs the 2nd_model folder next to this one (or STS2_SERVER pointing at 2nd_model/Server).
Runs in about two minutes; nothing is trained.
"""
import time

import numpy as np
from gymnasium.utils.env_checker import check_env

from collab_agent.config import EnvConfig, OBS_SIZE, A_PLAY0, A_CHOOSE0, A_STOP
from collab_agent.env import CollabEnv
from collab_agent.bots import make_bot
from collab_agent import real_engine as R
from collab_agent import styles
from GameEngine.Cards._card_ref import new_ref          # importable once real_engine found 2nd_model

REAL = EnvConfig(engine="real")


def scenario(lineup, agent_hand, mate_hand, seed=1):
    """A two-player fight against `lineup`, with these hands and 3 energy each."""
    seats = [R.Seat(0, list(R.STARTER)),
             R.Seat(1, list(R.STARTER), make_bot("aggressive", np.random.default_rng(0)))]
    rc = R.start_fight(lineup, seats, seed=seed)
    for ally, hand in zip(rc.allies, (agent_hand, mate_hand)):
        ally.hand = [new_ref(c) for c in hand]
        ally.energy = 3
    rc._sync()
    return rc


def test_every_lineup():
    """Every encounter in the pools starts with 2 to 4 players and plays out, every seat a bot."""
    rng = np.random.default_rng(1)
    results = {"win": 0, "lose": 0, None: 0}
    for i, lineup in enumerate(lineup for pool in R.POOLS.values() for lineup in pool):
        n = 2 + i % 3
        seats = R.make_team(rng, [make_bot("cheese", rng) for _ in range(n - 1)], REAL)
        seats[0].bot = make_bot("aggressive", rng)            # the agent's seat played by a bot too
        rc = R.start_fight(lineup, seats, seed=i)
        assert rc.result is None and rc.living_enemies(), lineup
        while rc.result is None and rc.turn <= 30:
            turn = rc.turn
            for s in range(n):
                rc.bot_finish_turn(s)
            assert rc.turn > turn or rc.result is not None, f"{lineup}: the round did not end"
        results[rc.result] += 1
    print(f"ok  all {sum(results.values())} lineups play out with bots in every seat "
          f"({results['win']} won, {results['lose']} lost, {results[None]} past 30 rounds)")


def test_random_rollouts(episodes=60):
    """The env on the real engine: masks always accepted, inputs in range, the reward adds up."""
    env = CollabEnv(REAL, seed=0)
    rng = np.random.default_rng(0)
    obs, _ = env.reset()
    done_eps, steps, total, wins, seen, lineups = 0, 0, 0.0, 0, set(), set()
    t = time.time()
    while done_eps < episodes:
        assert obs.shape == (OBS_SIZE,) and obs.dtype == np.float32
        assert -1.0 <= obs.min() and obs.max() <= 1.0, "observation out of range"
        m = env.action_masks()
        assert m.any(), "mask has no legal action"
        obs, r, term, trunc, info = env.step(int(rng.choice(np.flatnonzero(m))))   # raises if refused
        steps += 1
        assert np.isfinite(r)
        total += info["reward_components"]["general"]
        if term:
            s = info["episode_summary"]
            assert abs(total - (s["score"] - env.start_score) / 100) < 1e-9
            seen.update(k for k in s if k.startswith("f_") and s[k] != 0)
            wins += s["win"]
            lineups.add(env.combat.lineup)
            done_eps, total = done_eps + 1, 0.0
            obs, _ = env.reset()
    rate = steps / (time.time() - t)
    assert {"f_baseline", "f_variant1", "f_variant2", "f_variant3"} & seen, seen
    print(f"ok  {episodes} random fights ({len(lineups)} lineups, {wins:.0f} won): masks always accepted, "
          f"inputs in [-1, 1], reward adds up; {rate:.0f} steps/s; scorings that fired: {sorted(seen)}")


def test_questions(episodes=25):
    """Cards that ask (one pick, or "up to" with Stop) go through Divide and Conquer."""
    env = CollabEnv(REAL, seed=3)
    rng = np.random.default_rng(3)
    env.reset()
    env.players[0].deck = R.STARTER + ["armaments", "purity", "burning_pact", "headbutt", "dual_wield",
                                       "discovery", "true_grit", "armaments"]
    env.reset()
    asked = stopped = 0
    done_eps = 0
    while done_eps < episodes:
        m = env.action_masks()
        if env.dc is not None:
            asked += 1
            assert not m[:A_CHOOSE0].any() and m[A_CHOOSE0:A_STOP].any()
        a = int(rng.choice(np.flatnonzero(m)))
        stopped += a == A_STOP
        _, _, term, _, _ = env.step(a)
        if term:
            done_eps += 1
            env.reset()
    assert asked > 20 and stopped > 0, (asked, stopped)
    print(f"ok  questions: {asked} asked through Divide and Conquer, {stopped} stopped, in {episodes} fights")


def test_knocked_out_with_a_question():
    """Two rounds that never ended in the 8-process stress test: a player knocked out while its
    card's question is open, and an agent knocked out by its own play after everyone else ended.
    Neither holds the round up, and the env plays the fight out without the agent."""
    rc = scenario(("nibbit",), ["burning_pact", "strike", "defend"], ["strike"])
    assert rc.play(0, 0, 0) is not None
    rc.allies[0].current_hp = 0
    rc._sync()
    rc.end_turn(1)
    assert rc.combat.choice_for(rc.allies[0]) is None and (rc.turn == 2 or rc.result is not None), rc.stall_report()

    env = CollabEnv(REAL, seed=2)
    env.reset()
    c = env.combat
    c.allies[0].hand = [new_ref(x) for x in ("burning_pact", "strike", "defend")]
    c.allies[0].energy = 3
    c._sync()
    real_play = c.play

    def fatal_play(seat, h, t):                 # the play opens its question, then knocks the agent out
        q = real_play(seat, h, t)
        c.allies[0].current_hp = 0
        c._sync()
        return q
    c.play = fatal_play
    assert env.action_masks()[A_PLAY0]
    _, _, term, _, _ = env.step(A_PLAY0)        # Burning Pact on no target
    assert term and env.dc is None, c.stall_report()

    # the teammate has ended; the agent's Bloodletting knocks it out: nobody is left to end the round
    rc = scenario(("nibbit",), ["bloodletting", "strike"], ["strike"])
    rc.end_turn(1)
    rc.allies[0].current_hp = 2
    rc._sync()
    rc.play(0, 0, 0)
    assert not rc.allies[0].is_alive() and (rc.turn == 2 or rc.result is not None), rc.stall_report()
    print("ok  knocked out mid-play: a question it held is forfeited, and the round ends "
          "when only players who have ended are left")


def test_about_to_blow():
    """A Waterfall Giant brought down holding Steam keeps 999,999,999 HP until it explodes. The
    smoke run's reward once swung by about 600,000 there (D at 999,999,999 / 240), which set
    VecNormalize's scale for the rest of training. It counts as beaten: 0 of its own max HP."""
    from GameEngine.Effects.StatusEffects.steam_eruption import SteamEruption
    from collab_agent import final_reward as FR
    from collab_agent.observation import encode
    rc = scenario(("waterfallgiant",), ["strike"], ["strike"])
    giant = rc.combat.enemies[0]
    entered = rc.entered[giant.unit_id]
    giant.apply_status(SteamEruption(source=giant, target=giant, amount=5))
    giant.current_hp = 3
    rc._sync()
    rc.play(0, 0, 4)                                   # the agent's Strike brings it down
    assert giant.blowing == "pending" and giant.current_hp == giant.BLOWN_HP and rc.result is None
    view = rc.living_enemies()[0]
    assert view.hp == 0 and view.max_hp == entered, (view.hp, view.max_hp, entered)
    fight = dict(win=False, lost=False, ally_hp=sum(p.hp for p in rc.living_players()),
                 ally_max_hp=sum(p.max_hp for p in rc.living_players()), allies_alive=2, allies=2,
                 enemy_hp=sum(e.hp for e in rc.living_enemies()), enemy_max_hp=rc.total_enemy_max_hp, turns=rc.turn)
    assert FR.general_penalty(fight, FR.PenaltyWeights())[1]["pen_D"] == 0
    obs = encode(rc, {1: dict(A=0.0, S=0.0, T=0.0, c_A=0.0, c_S=0.0, c_T=0.0)})
    assert -1.0 <= obs.min() and obs.max() <= 1.0
    print("ok  Waterfall Giant about to blow: beaten (0 HP of its own max), D and the inputs stay in range")


def test_collaboration_stats():
    """The numbers the collaborative scorings read, on set-up hands."""
    # Bash on e1, then the teammate's Strike: 6 becomes 9 on the Vulnerable, 3 of it the agent's
    rc = scenario(("nibbit",), ["bash"], ["strike"])
    rc.play(0, 0, 4)
    rc.play(1, 0, 4)
    st = rc.stats
    assert st["vuln_applied"] == 1 and st["vuln_cashed"] == 1 and st["bonus_damage"] == 3, st
    # both Bashed: the agent owns half the stacks, so half the 3
    rc = scenario(("nibbit",), ["bash", "strike"], ["bash"])
    rc.play(1, 0, 4)
    rc.play(0, 0, 4)
    rc.play(0, 0, 4)
    assert rc.stats["vuln_cashed"] == 0                         # the agent's own Strike: not a teammate's hit
    rc2 = scenario(("nibbit",), ["bash"], ["bash", "strike"])
    rc2.play(1, 0, 4)
    rc2.play(0, 0, 4)
    rc2.play(1, 0, 4)
    assert abs(rc2.stats["bonus_damage"] - 1.5) < 1e-9 and abs(rc2.stats["vuln_cashed"] - 0.5) < 1e-9, rc2.stats
    # Shockwave's Weak on the Nibbit's Butt (12): the teammate, with no Block, takes 9, not 12
    rc = scenario(("nibbit",), ["shockwave"], ["strike"])
    assert rc.enemies[0].intent.damage_to["p2"] == 12, rc.enemies[0].intent.damage_to
    rc.play(0, 0, 0)
    rc.end_turn(0)
    rc.end_turn(1)
    st = rc.stats
    assert st["weak_applied"] == 1 and st["weak_cashed"] == 1 and st["hp_saved"] == 3, st
    assert rc.finished_histories.keys() == {0, 1} and rc.turn == 2
    # Lift's 11 Block on the teammate: of the Butt's 12, 11 kept
    rc = scenario(("nibbit",), ["lift"], ["strike"])
    rc.play(0, 0, 1)
    assert rc.stats["block_to_ally"][1] == 11 and rc.agent_block[1] == 11
    rc.end_turn(0)
    rc.end_turn(1)
    assert rc.stats["block_cashed"] == 1 and rc.stats["hp_saved"] == 11 and rc.agent_block[1] == 0, rc.stats
    print("ok  collaboration numbers: Vulnerable share and bonus, Weak and Block saving a teammate HP")


def test_history():
    """What the analyzer gets is aura's turn, as the real game logs it."""
    rc = scenario(("nibbit",), ["strike", "strike", "defend", "defend", "bash"], ["defend"])
    rc.end_turn(1)                       # the teammate does nothing
    rc.play(0, 0, 4)
    rc.play(0, 0, 4)
    rc.end_turn(0)
    h = rc.finished_histories[0]
    assert h["E_total"] == 3 and [u[1] for u in h["used"]] == [6, 6] and h["intent"] == 12, h
    assert len(h["opp"]) >= 2 and h["end_block"] == 0
    print("ok  analyzer input: the used cards as shown, Opp, the hit coming and Block at turn end")


def test_profiles(fights=20):
    """The analyzer tells an aggressive teammate from a defensive one on the real engine."""
    found = {}
    for kind in ("aggressive", "defensive"):
        env = CollabEnv(EnvConfig(engine="real", team_fights=fights + 1), seed=5, fixed_team=[kind])
        bot = make_bot("cheese", None)
        env.reset()
        done = 0
        while done < fights:
            _, _, term, _, _ = env.step(styles.cheese_action(env, bot))
            if term:
                done += 1
                env.reset()
        found[kind] = env.team_profiles.get(1)["A"]
    assert found["aggressive"] > 0.3 and found["defensive"] < -0.3, found
    print(f"ok  profiles on the real engine: aggressive A={found['aggressive']:+.2f}, "
          f"defensive A={found['defensive']:+.2f}")


def test_blend_bot(teams=30):
    """Blend teammates on the real engine: fights play out, and their profiles spread wider than
    the named styles', with some on the build-up side (S above 0) that none of those reach."""
    env = CollabEnv(EnvConfig(engine="real", team_fights=6), seed=8, fixed_team=["blend"])
    bot = make_bot("cheese", None)
    env.reset()
    found = []
    while len(found) < teams:
        _, _, term, _, _ = env.step(styles.cheese_action(env, bot))
        if term:
            if env.fights_left <= 0:
                found.append(dict(env.team_profiles.get(1)))
            env.reset()
    spread = {k: (min(p[k] for p in found), max(p[k] for p in found)) for k in "AST"}
    assert max(p["S"] for p in found) > 0, spread
    assert spread["A"][1] - spread["A"][0] > 0.5, spread
    print("ok  blend teammates on the real engine, profile range over " + str(teams) + " teams: " +
          "  ".join(f"{k} {lo:+.2f} to {hi:+.2f}" for k, (lo, hi) in spread.items()))


def test_decks(fights=40):
    """--deck: every seat plays exactly that deck in every fight, and fights play out with its cards.
    --extra-cards: that many random cards on the starter. Wrong settings are refused."""
    from train import build_config
    deck = R.FIXED_DECKS["teamwork"]
    assert build_config(engine="real", deck="teamwork").real_deck == deck and len(deck) == 24
    env = CollabEnv(build_config(engine="real", deck="teamwork"), seed=6)
    rng = np.random.default_rng(6)
    obs, _ = env.reset()
    done_fights, seen = 0, set()
    while done_fights < fights:
        assert -1.0 <= obs.min() and obs.max() <= 1.0, "observation out of range"
        assert all(sorted(s.deck) == sorted(deck) for s in env.players)
        seen.update(c.defn.name for p in env.combat.players if p is not None for c in p.hand)
        obs, _, term, _, _ = env.step(int(rng.choice(np.flatnonzero(env.action_masks()))))
        if term:
            done_fights += 1
            obs, _ = env.reset()
    assert {"Lift", "Coordinate", "Believe in You"} <= seen, seen
    env = CollabEnv(build_config(engine="real", extra_cards=14), seed=6)
    env.reset()
    assert all(len(s.deck) == len(R.STARTER) + 14 for s in env.players)
    env = CollabEnv(build_config(engine="real", deck="teamwork", pool_weights=(0, 0.5, 0.5)), seed=6)
    lineups = set()
    for _ in range(80):
        env.reset()
        lineups.add(env.combat.lineup)
    assert lineups <= set(R.ELITES) | set(R.BOSSES), lineups
    assert lineups & set(R.ELITES) and lineups & set(R.BOSSES), lineups        # both kinds come up
    for bad in (dict(engine="real", deck="nope"), dict(engine="real", deck="teamwork", extra_cards=3), dict(deck="teamwork"),
                dict(pool_weights=(0, 1, 0)), dict(engine="real", pool_weights=(0, 0, 0)),
                dict(engine="real", pool_weights=(-1, 1, 1))):
        try:
            build_config(**bad)
            raise AssertionError(f"{bad} must be refused")
        except ValueError:
            pass
    print(f"ok  decks: --deck gives every seat exactly that deck ({fights} fights played), --extra-cards adds random cards")


def test_deck_presets(teams=60, fights=20):
    """--deck-presets: each new team is dealt one of the named kinds of deck: the whole deck for every seat, or a preset,
    each seat its own deck with that preset's number of cards of each kind, all from the whole deck. The presets are the
    playtest's. Off by default: every seat the whole deck, and the same draws as before. Wrong settings are refused."""
    import dataclasses
    import json
    from collections import Counter
    import evaluate as EV
    import playtest as PT
    from train import build_config
    whole = R.FIXED_DECKS["teamwork"]
    names = (R.WHOLE_DECK, *R.DECK_PRESETS)
    assert R.DECK_PRESETS == PT.DECK_PRESETS, "real_engine.DECK_PRESETS and playtest.DECK_PRESETS must stay the same"
    assert {k: sorted(v) for k, v in R.card_kinds(whole).items()} == {k: sorted(v) for k, v in PT.card_kinds(R, whole).items()}
    assert EnvConfig().real_deck_presets is None and build_config(engine="real", deck="teamwork").real_deck_presets is None
    cfg = build_config(engine="real", deck="teamwork", deck_presets=[n.lower() for n in names])      # any case is accepted
    assert cfg.real_deck_presets == names
    assert EV.config_from_dict(json.loads(json.dumps(dataclasses.asdict(cfg)))).real_deck_presets == list(names)   # saved and loaded

    kind_of = {}
    for kind, cards in R.card_kinds(whole).items():
        if kind != "helper":
            for c in cards:
                kind_of[c] = kind
    env = CollabEnv(dataclasses.replace(cfg, team_fights=1), seed=6)
    dealt, own = Counter(), 0
    for _ in range(teams):
        env.reset()
        preset = env.players[0].preset
        assert preset in names and all(s.preset == preset for s in env.players)
        dealt[preset] += 1
        for s in env.players:
            if preset == R.WHOLE_DECK:
                assert sorted(s.deck) == sorted(whole)
                continue
            want = R.DECK_PRESETS[preset]
            assert len(s.deck) == sum(want.values()) and set(s.deck) <= set(whole), (preset, s.deck)
            got = Counter(kind_of[c] for c in s.deck)
            assert got["attack"] == want["attack"] and got["power"] == want["power"], (preset, got)
            assert got["block"] + got["skill"] == want["block"] + want["skill"] + want.get("helper", 0), (preset, got)
        own += preset != R.WHOLE_DECK and sorted(env.players[0].deck) != sorted(env.players[1].deck)
    assert set(dealt) == set(names), dealt                    # every kind comes up
    assert own >= (teams - dealt[R.WHOLE_DECK]) * 0.8, own     # and each seat gets its own deck

    rng = np.random.default_rng(6)                            # fights play out on dealt decks
    env = CollabEnv(build_config(engine="real", deck="teamwork", deck_presets=["Small", "Bloated", "Helper"]), seed=7)
    obs, _ = env.reset()
    done_fights = 0
    while done_fights < fights:
        assert -1.0 <= obs.min() and obs.max() <= 1.0, "observation out of range"
        obs, _, term, _, _ = env.step(int(rng.choice(np.flatnonzero(env.action_masks()))))
        if term:
            done_fights += 1
            obs, _ = env.reset()

    plain, off = CollabEnv(build_config(engine="real", deck="teamwork"), seed=6), CollabEnv(dataclasses.replace(cfg, real_deck_presets=None), seed=6)
    for _ in range(12):                                       # off: the whole deck, and the same fights as a run without the setting
        plain.reset(), off.reset()
        assert all(sorted(s.deck) == sorted(whole) and s.preset is None for s in off.players)
        assert plain.combat.lineup == off.combat.lineup and [p.hp for p in plain.combat.players if p] == [p.hp for p in off.combat.players if p]
    for bad in (dict(engine="real", deck_presets=["Small"]), dict(engine="real", deck="teamwork", deck_presets=["Tiny"]),
                dict(deck_presets=["Small"])):
        try:
            build_config(**bad)
            raise AssertionError(f"{bad} must be refused")
        except ValueError:
            pass
    print(f"ok  --deck-presets: {teams} teams dealt {dict(dealt)}, each seat its own deck with the preset's cards of each kind, "
          f"{fights} fights played, saved and loaded; off by default")


def test_pool_decks(teams=60, fights=12):
    """Pool in --deck-presets: a team dealt it gets, each seat, the starter and --pool-cards different cards from the whole
    card pool; the other kinds are dealt as before. Without Pool, nothing changes. Wrong settings are refused."""
    import dataclasses
    import json
    from collections import Counter
    import evaluate as EV
    from train import build_config
    whole, pool = R.FIXED_DECKS["teamwork"], set(R.card_pool())
    assert R.POOL_DECK not in R.DECK_PRESETS, "Pool is not one of the playtest's presets"
    assert EnvConfig().real_pool_cards == 8 and build_config(engine="real", deck="teamwork", deck_presets=["Pool"]).real_pool_cards == 8
    cfg = build_config(engine="real", deck="teamwork", deck_presets=["whole", "pool"], pool_cards=6)    # any case is accepted
    assert cfg.real_deck_presets == (R.WHOLE_DECK, R.POOL_DECK) and cfg.real_pool_cards == 6
    back = EV.config_from_dict(json.loads(json.dumps(dataclasses.asdict(cfg))))                           # saved and loaded
    assert back.real_deck_presets == [R.WHOLE_DECK, R.POOL_DECK] and back.real_pool_cards == 6

    env = CollabEnv(dataclasses.replace(cfg, team_fights=1), seed=9)
    dealt, own, new_cards = Counter(), 0, set()
    for _ in range(teams):
        env.reset()
        preset = env.players[0].preset
        assert all(s.preset == preset for s in env.players)
        dealt[preset] += 1
        for s in env.players:
            if preset == R.WHOLE_DECK:
                assert sorted(s.deck) == sorted(whole)
                continue
            extra = s.deck[len(R.STARTER):]
            assert s.deck[:len(R.STARTER)] == R.STARTER and len(extra) == 6 and len(set(extra)) == 6 and set(extra) <= pool, s.deck
            new_cards |= set(extra) - set(whole)
        own += preset == R.POOL_DECK and sorted(env.players[0].deck) != sorted(env.players[1].deck)
    assert set(dealt) == {R.WHOLE_DECK, R.POOL_DECK}, dealt
    assert own >= dealt[R.POOL_DECK] * 0.8, own                 # each seat its own pool cards
    assert len(new_cards) >= 30, len(new_cards)                 # and they reach well past the whole deck's cards

    rng = np.random.default_rng(9)                             # fights play out on pool decks
    env = CollabEnv(build_config(engine="real", deck="teamwork", deck_presets=["Pool"]), seed=10)
    obs, _ = env.reset()
    done_fights = 0
    while done_fights < fights:
        assert -1.0 <= obs.min() and obs.max() <= 1.0, "observation out of range"
        obs, _, term, _, _ = env.step(int(rng.choice(np.flatnonzero(env.action_masks()))))
        if term:
            done_fights += 1
            obs, _ = env.reset()

    with_presets = build_config(engine="real", deck="teamwork", deck_presets=["Whole", "Default", "Small", "Bloated", "Helper"])
    a, b = CollabEnv(with_presets, seed=6), CollabEnv(dataclasses.replace(with_presets, real_pool_cards=3), seed=6)
    for _ in range(12):                                        # without Pool, real_pool_cards changes nothing: same decks, same fights
        a.reset(), b.reset()
        assert [sorted(s.deck) for s in a.players] == [sorted(s.deck) for s in b.players] and a.combat.lineup == b.combat.lineup
    for bad in (dict(engine="real", deck="teamwork", pool_cards=8), dict(engine="real", deck="teamwork", deck_presets=["Whole"], pool_cards=8),
                dict(engine="real", deck="teamwork", deck_presets=["Pool"], pool_cards=-1),
                dict(engine="real", deck="teamwork", deck_presets=["Pool"], pool_cards=len(pool) + 1)):
        try:
            build_config(**bad)
            raise AssertionError(f"{bad} must be refused")
        except ValueError:
            pass
    print(f"ok  Pool decks: {teams} teams dealt {dict(dealt)}, each seat the starter and its own pool cards "
          f"({len(new_cards)} cards beyond the whole deck seen), {fights} fights played, saved and loaded; nothing changes without Pool")


def test_tag_bots(fights=8):
    """Scale, now, self and team bots: each plays its own kind of card first, anything else when it
    has none (never wasting the turn), the scale bot only for its first turns; fights play out."""
    from train import build_config

    def first_card(kind, hand, turns_left=None):
        rc = scenario(("nibbit",), ["strike"], hand)
        bot = make_bot(kind, np.random.default_rng(0))
        if turns_left is not None:
            bot.build_turns = turns_left
        action = bot.act(rc, 1)
        assert action[0] == "play", (kind, hand, action)
        return str(rc.allies[1].hand[action[1]])

    assert first_card("scale", ["strike", "inflame"], 1) == "inflame"          # turn 1 of 1: building up
    assert first_card("scale", ["strike", "inflame"], 0) == "strike"           # past its build-up turns
    assert first_card("scale", ["strike", "defend"], 1) == "strike"            # nothing to build with: not a wasted turn
    assert first_card("now", ["inflame", "strike"]) == "strike"
    assert first_card("now", ["inflame"]) == "inflame"                         # only a Power left: still plays
    assert first_card("self", ["strike", "defend"]) == "defend"
    assert first_card("team", ["defend", "strike"]) == "strike"
    rolled = {make_bot("scale", np.random.default_rng(i)).build_turns for i in range(40)}
    assert rolled == {2, 3, 4}, rolled
    cfg = build_config(engine="real", deck="teamwork")
    for kind in ("scale", "now", "self", "team"):
        env = CollabEnv(cfg, seed=5, fixed_team=[kind, kind])
        rng = np.random.default_rng(5)
        obs, _ = env.reset()
        done = 0
        while done < fights:
            assert -1.0 <= obs.min() and obs.max() <= 1.0
            obs, _, term, _, _ = env.step(int(rng.choice(np.flatnonzero(env.action_masks()))))
            if term:
                done += 1
                obs, _ = env.reset()
    print("ok  scale, now, self, team bots: their own cards first, no wasted turns, scale only for its first 2-4 turns")


def test_continuous_and_history(teams=40):
    """On the real engine, with the teamwork deck: the analyzer reads a continuous bot's x (A rises
    with it), and with history the agent's first fight already shows that profile."""
    from train import build_config
    env = CollabEnv(build_config(engine="real", deck="teamwork", history_fights=10), seed=3, fixed_team=["continuous"])
    xs, a = [], []
    for _ in range(teams):
        env.players = None
        env.reset()
        xs.append(env.players[1].bot.x), a.append(env.team_profiles.get(1)["A"])
    r = np.corrcoef(xs, a)[0, 1]
    assert r > 0.7, (r, xs, a)
    fresh = CollabEnv(build_config(engine="real", deck="teamwork"), seed=3, fixed_team=["continuous"])
    fresh.reset()
    assert fresh.team_profiles.get(1)["A"] == 0
    print(f"ok  continuous + history on the real engine: A follows x (correlation {r:.2f}) before the first fight; fresh starts at 0")


def test_no_wait_and_blind(fights=10):
    """Teammates act only after the agent ends its turn, their cards shown (--no-wait) or hidden
    (--blind-teammates); fights still finish and profiles still build."""
    from train import build_config
    from collab_agent.config import OFF_CARDS, OFF_PILES, HAND_SIZE, CARD_SIZE, N_PLAYERS, N_PILES, PILE_SIZE, A_WAIT, A_END
    mates = (OFF_CARDS + HAND_SIZE * CARD_SIZE, OFF_CARDS + N_PLAYERS * HAND_SIZE * CARD_SIZE)
    piles = OFF_PILES + N_PILES * PILE_SIZE
    calls = []
    cls = original = None
    try:
        for hidden, rule in ((False, dict(no_wait=True)), (True, dict(blind_teammates=True))):
            cfg = build_config(engine="real", deck="teamwork", pool_weights=(0, 0.5, 0.5), **rule)
            env = CollabEnv(cfg, seed=5, fixed_team=["aggressive", "defensive"])
            rng = np.random.default_rng(5)
            env.reset()
            if cls is None:
                cls, original = type(env.combat), type(env.combat).bot_step
                cls.bot_step = lambda self, seat: (calls.append(seat), original(self, seat))[1]
            for _ in range(fights):
                calls.clear()
                obs, _ = env.reset()
                assert not calls, "a teammate acted before the agent's first look"
                assert obs[OFF_CARDS:mates[0]].any(), "the agent must still see its own hand"
                assert bool(obs[mates[0]:mates[1]].any()) != hidden and bool(obs[piles:].any()) != hidden
                done = False
                while not done:
                    mask = env.action_masks()
                    assert not mask[A_WAIT]
                    if hidden:
                        assert not obs[mates[0]:mates[1]].any() and not obs[piles:].any()
                    action, turn = int(rng.choice(np.flatnonzero(mask))), env.combat.turn
                    calls.clear()
                    obs, _, done, _, _ = env.step(action)
                    if action != A_END and not done and env.combat.turn == turn and env.combat.players[0].alive:
                        assert not calls, "a teammate acted during the agent's turn"
                assert env.team_profiles.get(1)["A"] != 0, "teammates must still build a profile"
    finally:
        if cls is not None:
            cls.bot_step = original
    print(f"ok  --no-wait and --blind-teammates on the real engine: no Wait, teammates act after the agent, cards shown or hidden, {fights} fights each, profiles build")


def test_start_hp(fights=30):
    """--start-hp: each player's HP is drawn separately at each fight start and the agent sees it; off by default;
    the reward pays only for what changes after the start; a saved run loads with it."""
    import json
    from dataclasses import asdict
    from train import build_config, percents
    from evaluate import config_from_dict
    from collab_agent.config import OFF_PLAYERS, PLAYER_SIZE
    assert build_config().start_hp is None and percents("100,50,10") == (1.0, 0.5, 0.1)
    for bad in (dict(start_hp=(0.5,)), dict(engine="real", start_hp=(1.5,)), dict(engine="real", start_hp=(0.0,))):
        try:
            build_config(**bad)
        except ValueError:
            continue
        raise AssertionError(f"build_config should refuse {bad}")
    team = ["aggressive", "defensive"]
    base = dict(engine="real", deck="teamwork", pool_weights=(0, 0.5, 0.5), collab_w=(0, 0, 0))
    env = CollabEnv(build_config(**base), seed=9, fixed_team=team)
    for _ in range(5):
        env.reset()
        assert all(p.hp == p.max_hp for p in env.combat.players if p is not None)
    levels = (1.0, 0.75, 0.5, 0.25, 0.1)
    cfg = config_from_dict(json.loads(json.dumps(asdict(build_config(start_hp=levels, **base)))))  # as a saved run loads
    env = CollabEnv(cfg, seed=9, fixed_team=team)
    rng = np.random.default_rng(9)
    seen, uneven = set(), 0
    for _ in range(fights):
        obs, _ = env.reset()
        players = [p for p in env.combat.players if p is not None]
        hp = [p.hp for p in players]
        assert hp == list(env.combat._hp), "HP lost must count from the starting HP"
        assert set(hp) <= {max(1, round(p.max_hp * s)) for p in players for s in levels}, hp
        for seat, p in enumerate(players):
            assert abs(obs[OFF_PLAYERS + seat * PLAYER_SIZE + 3] - p.hp / p.max_hp) < 1e-5, "the agent must see each player's HP"
        seen |= set(hp)
        uneven += len(set(hp)) > 1
        start, paid, done = env.start_score, 0.0, False
        while not done:
            obs, reward, done, _, info = env.step(int(rng.choice(np.flatnonzero(env.action_masks()))))
            paid += reward
        assert abs(paid - (info["episode_summary"]["score"] - start) / 100) < 1e-6, "the start must not be paid or charged"
    assert len(seen) == len(levels) and uneven > fights / 2, (seen, uneven)
    first, second = [CollabEnv(cfg, seed=11, fixed_team=team) for _ in range(2)]
    first.reset(), second.reset()
    assert [p.hp for p in first.combat.players if p] == [p.hp for p in second.combat.players if p], "same seed, same HP"
    print(f"ok  --start-hp: HP drawn per player ({uneven} of {fights} fights uneven), seen by the agent, not paid for, saved and loaded; off by default")


def test_cards_shown_true():
    """Lift shows its Block on the teammate and Intercept on the player, as the engine gives it; the bots weigh Lift
    as Block; --team-penalty pays each step and is saved with the run."""
    import json
    from dataclasses import asdict
    from train import build_config
    from evaluate import config_from_dict
    from collab_agent import observation as O
    from collab_agent.bots import CheeseBot
    from collab_agent.config import CARD_SIZE, OUTCOME_SIZE
    rc = scenario(("nibbit",), ["lift", "intercept", "rally", "defend"], ["strike"] * 3)
    me = rc.players[0]
    expect = {"Lift": (1, 11), "Intercept": (0, 9), "Rally": (2, 12), "Defend": (0, 5)}
    for card in me.hand:
        v = np.zeros(CARD_SIZE, dtype=np.float32)
        O.write_card(v, 0, rc, me, card)
        shown = [float(v[19 + r * OUTCOME_SIZE + 2]) for r in range(4)]
        where, amount = expect[card.name]
        assert card.blk == amount and card.defn.block == amount, card.name
        assert abs(shown[where] - amount / (amount + 5)) < 1e-6 and sum(x > 0 for x in shown) == 1, (card.name, shown)
    # what the input says is what the engine does
    slot = {c.name: i for i, c in enumerate(me.hand)}
    rc.play(0, slot["Lift"], 1)
    assert (rc.players[0].block, rc.players[1].block) == (0, 11)
    slot = {c.name: i for i, c in enumerate(rc.players[0].hand)}
    rc.play(0, slot["Intercept"], 1)
    assert (rc.players[0].block, rc.players[1].block) == (9, 11)
    # Cheese covers a teammate who needs it, and keeps Lift when nobody does
    rc = scenario(("nibbit",), ["lift"], ["strike"])
    assert rc.incoming(1) > 0 and CheeseBot().act(rc, 0) == ("play", 0, 1)
    rc.allies[1].block = 99
    rc._sync()
    assert CheeseBot().act(rc, 0) == ("end",)
    try:
        build_config(team_penalty=(15, 26), penalty=(35, 5, 5, 15, 5))
        raise AssertionError("weights not adding up to 100 must be refused")
    except ValueError:
        pass
    cfg = config_from_dict(json.loads(json.dumps(asdict(build_config(
        engine="real", deck="teamwork", pool_weights=(0, .5, .5), collab_w=(0, 0, 0), penalty=(35, 5, 5, 15, 5), team_penalty=(15, 25))))))
    assert (cfg.final.penalty.B_team, cfg.final.penalty.C_team) == (15, 25)
    env = CollabEnv(cfg, seed=4, fixed_team=["aggressive", "defensive"])
    rng = np.random.default_rng(4)
    for _ in range(12):
        env.reset()
        start, paid, done = env.start_score, 0.0, False
        while not done:
            _, reward, done, _, info = env.step(int(rng.choice(np.flatnonzero(env.action_masks()))))
            paid += reward
        s = info["episode_summary"]
        assert abs(paid - (s["score"] - start) / 100) < 1e-6
        assert 0 <= s["mates_alive"] <= 1 and s["self_alive"] in (0.0, 1.0) and "score_std" in s
    print(f"ok  cards: Lift and Intercept shown as the engine gives them; Cheese covers a teammate in need and keeps Lift otherwise; --team-penalty pays each step and is saved")


def test_sort_teammates(fights=12):
    """--sort-teammates: slot 1 is the teammate most at risk at every decision, all their numbers move with them, a
    target in an action means the teammate in that slot, and the Cheese bot plays the same fights. Off by default."""
    import json
    from dataclasses import asdict, replace
    from train import build_config
    from evaluate import config_from_dict, policy_cheese
    from collab_agent.config import A_CHOOSE0, N_TARGETS, N_PLAYERS, OFF_PLAYERS, PLAYER_SIZE, OFF_ENEMIES, OFF_CARDS, HAND_SIZE, CARD_SIZE, OFF_PILES, N_PILES, PILE_SIZE
    from collab_agent.observation import encode
    base = dict(engine="real", deck="teamwork", pool_weights=(0, .5, .5), collab_w=(0, 0, 0), start_hp=(1.0, 0.5, 0.25))
    assert build_config().sort_teammates is False
    cfg = config_from_dict(json.loads(json.dumps(asdict(build_config(sort_teammates=True, **base)))))   # as a saved run loads
    assert cfg.sort_teammates is True
    env = CollabEnv(cfg, seed=6, fixed_team=["aggressive", "defensive"])
    rng = np.random.default_rng(6)
    decisions = moved = 0
    for _ in range(fights):
        obs, _ = env.reset()
        start, paid, done = env.start_score, 0.0, False
        while not done:
            c = env.combat
            raw = encode(c, env.team_profiles.values, env.dc.group if env.dc is not None else (), env.waited)
            assert np.array_equal(obs[:OFF_PLAYERS + PLAYER_SIZE], raw[:OFF_PLAYERS + PLAYER_SIZE]), "the agent's own numbers stay"
            assert np.array_equal(obs[OFF_ENEMIES:OFF_CARDS + HAND_SIZE * CARD_SIZE], raw[OFF_ENEMIES:OFF_CARDS + HAND_SIZE * CARD_SIZE])
            for slot, seat in enumerate(env.slots):
                for off, size in ((OFF_PLAYERS, PLAYER_SIZE), (OFF_CARDS, HAND_SIZE * CARD_SIZE), (OFF_PILES, N_PILES * PILE_SIZE)):
                    assert np.array_equal(obs[off + slot * size:off + (slot + 1) * size], raw[off + seat * size:off + (seat + 1) * size])
            living = [s for s in env.slots[1:] if s < len(c.players) and c.players[s] is not None and c.players[s].alive]
            left = [c.players[s].hp - max(0, c.incoming(s) - c.players[s].block) for s in living]
            assert left == sorted(left), left
            mask = env.action_masks()
            if env.dc is None and c.players[0].alive:
                plays = c.legal_plays(0)
                assert sum(mask[A_PLAY0:A_CHOOSE0]) == len(plays)
                assert all(mask[A_PLAY0 + N_TARGETS * h + env.target_slot(t)] for h, t in plays)
            decisions += 1
            moved += env.slots != list(range(N_PLAYERS))
            obs, reward, done, _, info = env.step(int(rng.choice(np.flatnonzero(mask))))
            paid += reward
        assert abs(paid - (info["episode_summary"]["score"] - start) / 100) < 1e-6
    assert moved, "teammates never moved out of seat order"
    # slot 1 is who the card reaches: seat 2 is the weak one here
    env.reset()
    c = env.combat
    c.set_start_hp([1.0, 1.0, 0.25])
    c.allies[1].block = 200                  # nothing gets through to seat 1, so seat 2 is the one at risk
    c.allies[0].hand = [new_ref("lift")]
    c.allies[0].energy = 3
    c._sync()
    env._obs()
    assert env.slots[:3] == [0, 2, 1], env.slots
    before = c.players[1].block, c.players[2].block
    env.step(A_PLAY0 + N_TARGETS * 0 + 1)
    assert (env.combat.players[1].block, env.combat.players[2].block) == (before[0], before[1] + 11)
    # the scripted bot's plays go through the slots and back: the same fights, sorted or not
    sorted_scores, plain_scores = [], []
    for setting, scores in ((True, sorted_scores), (False, plain_scores)):
        env = CollabEnv(replace(cfg, sort_teammates=setting), seed=9, fixed_team=["aggressive", "defensive"])
        act = policy_cheese()
        obs, _ = env.reset()
        while len(scores) < 8:
            obs, _, done, _, info = env.step(int(act(env, obs)))
            if done:
                scores.append(info["episode_summary"]["score"])
                obs, _ = env.reset()
    assert sorted_scores == plain_scores, (sorted_scores, plain_scores)
    check_env(CollabEnv(cfg, seed=3, strict=False), skip_render_check=True)
    print(f"ok  --sort-teammates: slot 1 most at risk over {decisions} decisions ({moved} out of seat order), numbers and targets move together, Cheese plays the same fights, saved and loaded; off by default")


def test_pair_network():
    """--network pair on the real engine: real inputs, the 24-card deck, two teammates."""
    from test_env import check_pair_training
    from train import build_config
    cfg = build_config(network="pair", engine="real", deck="teamwork", pool_weights=(0, .5, .5), collab_w=(0, 0, 0), timesteps=256,
                       teammates=["continuous"], start_hp=(1.0, 0.5, 0.25))
    size, decisions = check_pair_training(cfg, ["aggressive", "defensive"])
    print(f"ok  --network pair on the real engine: {size:,} parameters, all parts train, saved and loaded the same, legal over {decisions} decisions, swapped seats, cards and enemies swap scores")


def test_card_effects(fights=10):
    """--card-effects: what a card does beyond damage, Block and statuses, read from the sandbox; no two pool cards look alike
    with it; teammates' effects move with their hands; the rest of the input and the fights stay exactly as without; the pair
    network reads it and an agent trained without it loads and plays as before. Off by default."""
    import json
    import os
    from dataclasses import asdict, replace
    from sb3_contrib import MaskablePPO
    from train import build_config
    from evaluate import config_from_dict
    from test_env import check_pair_training
    from GameEngine.Cards._card_ref import CardRef
    from collab_agent.config import (OBS_SIZE_EFFECTS, OFF_EFFECTS, EFFECT_SIZE, EFFECT_NAMES, HAND_SIZE, N_PLAYERS, CARD_SIZE,
                                     OFF_PLAYERS, PLAYER_SIZE, OFF_CARDS, OFF_PILES, N_PILES, PILE_SIZE)
    from collab_agent.observation import encode, write_card, write_effects
    assert EnvConfig().card_effects is False and build_config().card_effects is False
    for bad in (dict(network="pair"), dict(engine="real")):         # mock engine; flat network
        try:
            build_config(card_effects=True, **bad)
            raise AssertionError(f"--card-effects must be refused with {bad}")
        except ValueError:
            pass
    try:
        CollabEnv(EnvConfig(card_effects=True))
        raise AssertionError("card effects on the mock engine must be refused")
    except ValueError:
        pass
    # what some cards do; a card's damage, Block and statuses are not repeated here
    expect = {"offering": dict(hp_lost=6, energy=2, draws=3), "bloodletting": dict(hp_lost=3, energy=2), "pommel_strike": dict(draws=1),
              "believe_in_you": dict(mate_energy=2), "huddle_up": dict(draws=2, mate_draws=2), "not_yet": dict(healed=10),
              "true_grit": dict(exhausts=1), "anger": dict(adds=1), "headbutt": dict(moves=1), "armaments": dict(improves=1),
              "havoc": dict(plays=1), "strike": {}, "defend": {}, "lift": {}, "inflame": {}, "wound": {}}
    for cid, want in expect.items():
        got = {k: v for k, v in zip(EFFECT_NAMES, R.card_effects(cid)) if v}
        assert got == want, (cid, got)
    assert R.card_effects(CardRef("offering", upgraded=True))[EFFECT_NAMES.index("draws")] == 5
    base = dict(engine="real", deck="teamwork", pool_weights=(0, .5, .5), collab_w=(0, 0, 0), network="pair", start_hp=(1.0, 0.5, 0.25))
    cfg = config_from_dict(json.loads(json.dumps(asdict(build_config(card_effects=True, **base)))))      # as a saved run loads
    assert cfg.card_effects is True
    # every pool card looks different to the agent with its effects (without them, some look exactly alike)
    env = CollabEnv(cfg, seed=4, fixed_team=["aggressive", "defensive"])
    env.reset()
    c, me = env.combat, env.combat.players[0]
    looks, plain = set(), set()
    for cid in R.card_pool():
        card = R._option_view(CardRef(cid), me.unit, 0)
        v = np.zeros(CARD_SIZE + EFFECT_SIZE, dtype=np.float32)
        write_card(v, 0, c, me, card)
        plain.add(v[:CARD_SIZE].tobytes())
        write_effects(v, CARD_SIZE, card)
        looks.add(v.tobytes())
    assert len(looks) == len(R.card_pool()) > len(plain), (len(looks), len(plain))
    # the same fights and the same input, with the effects after it; the effects are read mid-fight here (cache emptied)
    seen, steps = {}, 0
    for setting in (True, False):
        R._EFFECTS.clear()
        env = CollabEnv(replace(cfg, card_effects=setting), seed=9, fixed_team=["aggressive", "defensive"])
        rng, out, done_fights = np.random.default_rng(9), [], 0
        obs, _ = env.reset()
        while done_fights < fights:
            out.append(obs)
            if setting:                                               # each hand card's effects in its slot, empty slots 0
                for seat, p in enumerate(env.combat.players):
                    for h in range(HAND_SIZE):
                        want = np.zeros(EFFECT_SIZE, dtype=np.float32)
                        if p is not None and h < len(p.hand):
                            write_effects(want, 0, p.hand[h])
                        at = OFF_EFFECTS + (seat * HAND_SIZE + h) * EFFECT_SIZE
                        assert np.array_equal(obs[at:at + EFFECT_SIZE], want), (seat, h)
            obs, _, done, _, _ = env.step(int(rng.choice(np.flatnonzero(env.action_masks()))))
            if done:
                done_fights += 1
                obs, _ = env.reset()
        seen[setting] = out
    assert len(seen[True]) == len(seen[False])
    assert all(a.shape == (OBS_SIZE_EFFECTS,) and np.array_equal(a[:OBS_SIZE], b) and b.shape == (OBS_SIZE,)
               for a, b in zip(seen[True], seen[False])), "the input before the effects, and the fights, must not change"
    assert any(a[OFF_EFFECTS:].any() for a in seen[True]), "no card ever showed an effect"
    # --sort-teammates: a teammate's effects move with their hand
    env = CollabEnv(replace(cfg, sort_teammates=True), seed=6, fixed_team=["aggressive", "defensive"])
    rng, moved = np.random.default_rng(6), 0
    for _ in range(4):
        obs, _ = env.reset()
        done = False
        while not done:
            raw = encode(env.combat, env.team_profiles.values, env.dc.group if env.dc is not None else (), env.waited, card_effects=True)
            for slot, seat in enumerate(env.slots):
                for off, size in ((OFF_PLAYERS, PLAYER_SIZE), (OFF_CARDS, HAND_SIZE * CARD_SIZE), (OFF_PILES, N_PILES * PILE_SIZE),
                                  (OFF_EFFECTS, HAND_SIZE * EFFECT_SIZE)):
                    assert np.array_equal(obs[off + slot * size:off + (slot + 1) * size], raw[off + seat * size:off + (seat + 1) * size])
            moved += env.slots != list(range(N_PLAYERS))
            obs, _, done, _, _ = env.step(int(rng.choice(np.flatnonzero(env.action_masks()))))
    assert moved, "teammates never moved out of seat order"
    check_env(CollabEnv(cfg, seed=3, strict=False), skip_render_check=True)
    # the pair network reads them (every part trains, saved and loaded the same, card and seat swaps swap scores)
    size, decisions = check_pair_training(replace(cfg, final=replace(cfg.final, total_timesteps=256), teammate_types=("continuous",)),
                                          ["aggressive", "defensive"])
    # an agent trained without them still loads and reads the 327 card numbers it was trained on
    old = MaskablePPO.load("runs/pair_survive_1m_s1/final_model.zip", device="cpu") if os.path.exists("runs/pair_survive_1m_s1/final_model.zip") else None
    if old is not None:
        assert old.policy.features_extractor.card_reader[0][0].in_features == CARD_SIZE and not old.policy.features_extractor.with_effects
    print(f"ok  --card-effects: {len(looks)} pool cards all look different ({len(plain)} without), effects in each card's slot and moved "
          f"with sorted teammates, same input and fights as without over {len(seen[True])} decisions, pair network {size:,} "
          f"parameters trains and swaps scores; {'the best agent loads as before; ' if old is not None else ''}off by default")


def test_enemy_statuses():
    """--enemy-statuses: the Act 1 enemies' statuses STATUS_LIST lacks go in a block of their own at the end, after any card
    effects; the rest of the input and the fights stay exactly as without; the pair network reads it, alone or with card
    effects, and an agent trained without it loads as before. Off by default."""
    import json
    import os
    from dataclasses import asdict, replace
    from sb3_contrib import MaskablePPO
    from train import build_config
    from evaluate import config_from_dict
    from test_env import check_pair_training
    from collab_agent.config import (OBS_SIZE_EFFECTS, ENEMY_EXTRA_STATUSES, ENEMY_EXTRA_SIZE, N_ENEMIES, ENEMY_SIZE,
                                     enemy_extra_offset, obs_size)
    assert EnvConfig().enemy_statuses is False and build_config().enemy_statuses is False
    for bad in (dict(network="pair"), dict(engine="real")):          # mock engine; flat network
        try:
            build_config(enemy_statuses=True, **bad)
            raise AssertionError(f"--enemy-statuses must be refused with {bad}")
        except ValueError:
            pass
    try:
        CollabEnv(EnvConfig(enemy_statuses=True))
        raise AssertionError("enemy statuses on the mock engine must be refused")
    except ValueError:
        pass
    block = N_ENEMIES * ENEMY_EXTRA_SIZE
    base = dict(engine="real", deck="teamwork", pool_weights=(0, .5, .5), collab_w=(0, 0, 0), network="pair", start_hp=(1.0, 0.5, 0.25))
    cfg = config_from_dict(json.loads(json.dumps(asdict(build_config(enemy_statuses=True, **base)))))     # as a saved run loads
    assert cfg.enemy_statuses is True and obs_size(cfg) == OBS_SIZE + block
    assert obs_size(replace(cfg, card_effects=True)) == OBS_SIZE_EFFECTS + block
    # Waterfall Giant fights: the same fights and input with the block as without, and its Steam Eruption shows exactly when it has some
    orig, seen = R.start_fight, {}
    R.start_fight = lambda lineup, seats, ally="ironclad", seed=0: orig(("waterfallgiant",), seats, ally, seed)
    try:
        for setting, effects in ((True, False), (False, False), (True, True), (False, True)):
            env = CollabEnv(replace(cfg, enemy_statuses=setting, card_effects=effects), seed=9, fixed_team=["aggressive", "defensive"])
            rng, out, done_fights = np.random.default_rng(9), [], 0
            obs, _ = env.reset()
            while done_fights < 3:
                e = env.combat.enemies[0]
                out.append((obs, dict(R._statuses(e.unit)) if e is not None and e.alive else None))
                obs, _, done, _, _ = env.step(int(rng.choice(np.flatnonzero(env.action_masks()))))
                if done:
                    done_fights += 1
                    obs, _ = env.reset()
            seen[(setting, effects)] = out
    finally:
        R.start_fight = orig
    for effects in (False, True):
        on, off, at = seen[(True, effects)], seen[(False, effects)], enemy_extra_offset(effects)
        assert len(on) == len(off)
        assert all(a.shape == (at + block,) and b.shape == (at,) and np.array_equal(a[:at], b) for (a, _), (b, _) in zip(on, off)), \
            "the input before the enemy statuses, and the fights, must not change"
    steam = ENEMY_EXTRA_STATUSES.index("steam_eruption")
    shown = [(a[OBS_SIZE + steam], st.get("steam_eruption", 0)) for a, st in seen[(True, False)] if st is not None]
    assert any(v > 0 for v, _ in shown) and all((v > 0) == (s > 0) for v, s in shown), "Steam Eruption isn't shown as the giant has it"
    # the pair network reads it, alone and with card effects (every part trains, saved and loaded the same, swaps swap scores)
    short = dict(final=replace(cfg.final, total_timesteps=256), teammate_types=("continuous",))
    size, _ = check_pair_training(replace(cfg, **short), ["aggressive", "defensive"])
    both, _ = check_pair_training(replace(cfg, card_effects=True, **short), ["aggressive", "defensive"])
    old = MaskablePPO.load("runs/pair_survive_1m_s1/final_model.zip", device="cpu") if os.path.exists("runs/pair_survive_1m_s1/final_model.zip") else None
    if old is not None:
        x = old.policy.features_extractor
        assert x.enemy_reader[0][0].in_features == ENEMY_SIZE and not x.with_foes and not x.with_effects
    print(f"ok  --enemy-statuses: {ENEMY_EXTRA_SIZE} statuses per enemy at the end, same input and fights as without over "
          f"{len(seen[(True, False)])} decisions, Steam Eruption shown as held; pair network {size:,} parameters ({both:,} with card "
          f"effects) trains and swaps scores; {'the best agent loads as before; ' if old is not None else ''}off by default")


def test_bots_spare_their_hp():
    """Scripted teammates never play a card whose HP cost would knock them out (bots._kills_itself); above that HP they still do."""
    from collab_agent.bots import make_bot, _kills_itself
    seats = [R.Seat(0, ["offering"] * 10), R.Seat(1, ["offering"] * 10, make_bot("aggressive", np.random.default_rng(1)))]
    rc = R.start_fight(("nibbit",), seats, "ironclad", 5)
    for hp, plays in ((6, False), (3, False), (7, True), (50, True)):        # Offering: lose 6 HP
        rc.allies[1].current_hp = hp
        rc._sync()
        assert _kills_itself(rc, 1, rc.players[1].hand[0]) is (not plays), hp
        assert (seats[1].bot.act(rc, 1)[0] == "play") is plays, hp
    print("ok  scripted teammates don't knock themselves out with an HP cost (Offering at 6 HP or less), and play it above")


def test_gym_and_swap():
    check_env(CollabEnv(REAL, seed=1, strict=False), skip_render_check=True)
    from evaluate import run_with_advantage, policy_cheese
    refs = {k: {"A": a, "S": 0.0, "T": 0.0} for k, a in (("aggressive", 0.9), ("defensive", -0.7), ("cheese", -0.5),
                                                             ("random", 0.0), ("change", -0.6), ("support", 0.5))}
    r = run_with_advantage(REAL, ["aggressive", "defensive"], policy_cheese, 8, 3, refs)
    assert r["advantage"] == 0 and r["score"] == r["score_swapped"], r
    print("ok  gymnasium API check; the swapped-profile test runs (Cheese bot's advantage 0)")


if __name__ == "__main__":
    t = time.time()
    test_knocked_out_with_a_question()
    test_about_to_blow()
    test_collaboration_stats()
    test_history()
    test_every_lineup()
    test_random_rollouts()
    test_questions()
    test_profiles()
    test_blend_bot()
    test_decks()
    test_deck_presets()
    test_pool_decks()
    test_tag_bots()
    test_continuous_and_history()
    test_no_wait_and_blind()
    test_start_hp()
    test_cards_shown_true()
    test_sort_teammates()
    test_pair_network()
    test_card_effects()
    test_enemy_statuses()
    test_bots_spare_their_hp()
    test_gym_and_swap()
    print(f"all real-engine checks passed in {time.time() - t:.0f}s")
