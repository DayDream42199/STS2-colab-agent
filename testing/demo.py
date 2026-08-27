
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import random

from game_engine.entities import Player
from game_engine.cards import make_starter_deck, make_coop_support_deck, make_ironclad_pool_deck
from game_engine.enemies import make_nibbit, make_shrinker_beetle, make_fuzzy_wurm_crawler
from game_engine.combat import CombatEngine
from game_engine.env import CombatEnv


def run_ironclad_pool_smoke_test():
    """Play through every ported real Ironclad card once each against a
    punching bag enemy, to catch any that error out or behave oddly."""
    print("=" * 70)
    print("IRONCLAD CARD POOL SMOKE TEST (each real ported card, once)")
    print("=" * 70)

    p1 = Player("Ironclad", max_hp=9999, max_energy=10, deck=make_ironclad_pool_deck())
    enemies = [make_nibbit()]
    enemies[0].max_hp = enemies[0].hp = 100000
    engine = CombatEngine([p1], enemies, seed=1)
    engine.start_player_turn()
    p1.hand = list(p1.draw_pile)  # cheat: put the whole pool in hand at once
    p1.draw_pile = []

    for card in list(p1.hand):
        if card not in p1.hand or engine.is_over:
            continue
        p1.energy = p1.max_energy  # test harness only: don't let one X-cost card starve the rest
        alive_enemies = engine.enemies_alive()
        target = alive_enemies[0] if alive_enemies else None
        ok = engine.play_card(p1, card, target=target)
        if not ok:
            print(f"FAILED to play: {card.name}")
        if engine.is_over:
            break

    for line in engine.log[-40:]:
        print(line)
    print(f"\n(showing last 40 log lines; {len(engine.log)} total)")
    print()


def run_scripted_coop_demo():
    print("=" * 70)
    print("SCRIPTED 2-PLAYER COOP BATTLE (simple greedy policy)")
    print("=" * 70)

    p1 = Player("Ironclad", max_hp=80, max_energy=3, deck=make_starter_deck())
    p2 = Player("Vanguard", max_hp=65, max_energy=3, deck=make_coop_support_deck())
    enemies = [make_nibbit(), make_shrinker_beetle()]

    engine = CombatEngine([p1, p2], enemies, seed=42)
    engine.start_player_turn()

    max_rounds = 15
    round_i = 0
    while not engine.is_over and round_i < max_rounds:
        round_i += 1
        for player in (p1, p2):
            if not player.alive:
                continue
            # greedy policy: play cheapest-first playable card into the
            # lowest-hp enemy until out of energy or hand
            progressed = True
            while progressed and not engine.is_over:
                progressed = False
                playable = sorted(
                    engine.playable_cards(player),
                    key=lambda c: (1, 0) if c.current_cost(player) == "X" else (0, c.current_cost(player)),
                )
                if not playable:
                    break
                card = playable[0]
                target = None
                alive_enemies = engine.enemies_alive()
                if alive_enemies:
                    target = min(alive_enemies, key=lambda e: e.hp)
                engine.play_card(player, card, target=target)
                progressed = True
        if engine.is_over:
            break
        engine.end_player_turn()
        if engine.is_over:
            break
        engine.run_enemy_turn()
        if not engine.is_over:
            engine.start_player_turn()

    for line in engine.log:
        print(line)
    print()
    print(f"RESULT: {'VICTORY' if engine.victory else 'DEFEAT'} after {engine.turn_number} turns")
    print()


def run_random_rl_env_demo():
    print("=" * 70)
    print("RL ENV SMOKE TEST (random legal-action policy, single agent view)")
    print("=" * 70)

    def make_players():
        return [Player("Ironclad", 80, 3, make_starter_deck())]

    def make_enemies():
        return [make_fuzzy_wurm_crawler()]

    env = CombatEnv(make_players, make_enemies, seed=7)
    obs = env.reset()
    print("Initial observation vector:", obs)

    rng = random.Random(1)
    total_reward = 0.0
    steps = 0
    done = False
    while not done and steps < 200:
        mask = env.legal_action_mask()
        legal_ids = [i for i, m in enumerate(mask) if m > 0]
        action = rng.choice(legal_ids)
        obs, reward, done, info = env.step(action)
        total_reward += reward
        steps += 1

    print(f"Episode finished after {steps} steps. Total reward: {total_reward:.2f}")
    print("Last log lines:", info["log_tail"])
    print(f"Victory: {env.engine.victory}")


if __name__ == "__main__":
    run_ironclad_pool_smoke_test()
    run_scripted_coop_demo()
    run_random_rl_env_demo()
