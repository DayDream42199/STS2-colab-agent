# -*- coding: utf-8 -*-
"""The smallest interesting version of the game: Strike, Defend, one enemy.

WHY THIS EXISTS. The full game is 226 cards, 106 enemies, 181 actions and an
817-float observation. That is a hard first target for an agent and a hard
first read for a person. This strips it to the two cards everyone understands
and one enemy that does exactly one thing, so you can watch a whole fight go
past and see every rule that fired.

WHAT IT IS NOT: a second implementation of combat. Everything here runs on the
real CombatEngine with real Card objects -- this file only chooses a small
deck and a small enemy. That matters: a hand-written mini-battle would be a
second copy of the rules, and the two would drift the first time either
changed. Whatever you learn here is true of the real game.

Statuses, relics and potions are not "turned off" -- there is nothing to turn
off. The systems exist in the engine, but nothing in this file applies a
status, grants a relic or hands out a potion, so they stay inert. Add a card
that applies Vulnerable and it will simply work.

    python simple.py                # PLAY IT -- one fight, in the terminal
    python simple.py demo           # watch a scripted fight + a policy sweep

    from simple import battle, greedy
    result = battle(greedy, seed=0, verbose=True)
"""

from typing import Callable, List, Optional

from cards import Card, CardType, TargetMode, fx_strike, fx_defend
from combat import CombatEngine
from enemies import Enemy, IntentType, Move
from entities import Player, seed_content

# --- the two cards ---------------------------------------------------------
# Real Card objects with the real effect functions, so they resolve through
# the same damage and block pipeline every other card uses. The numbers are
# the game's own: Strike 6 damage, Defend 5 block, both cost 1.


def make_strike() -> Card:
    return Card("Strike", 1, CardType.ATTACK, TargetMode.SINGLE_ENEMY, fx_strike,
                values={"damage": 6}, description="Deal 6 damage.")


def make_defend() -> Card:
    return Card("Defend", 1, CardType.SKILL, TargetMode.SELF, fx_defend,
                values={"block": 5}, description="Gain 5 Block.")


def make_deck(strikes: int = 5, defends: int = 5) -> List[Card]:
    """A deck of nothing but Strikes and Defends.

    Ten cards and a five-card draw means you see half your deck every turn,
    which keeps the shuffle from being the thing that decides the fight."""
    return [make_strike() for _ in range(strikes)] + \
           [make_defend() for _ in range(defends)]


# --- the one enemy ---------------------------------------------------------

def make_dummy(hp: int = 40, damage: int = 8) -> Enemy:
    """An enemy with a single move: hit the player for a fixed amount.

    No statuses, no scaling, no phases, and its intent never changes -- so
    "how much damage is coming" is knowable and blocking is a real decision
    rather than a guess. It is the simplest thing that still makes Defend
    worth playing."""
    def attack(engine, enemy):
        dealt = enemy.deal_attack_damage(damage)
        engine.pick_enemy_attack_target().take_damage(
            dealt, log=engine.log, label=enemy.name, attacker=enemy)

    move = Move("Hit", IntentType.ATTACK, attack, damage=damage)
    # choose_move(enemy, turn) -> Move. It only has one, so turn is ignored.
    return Enemy("Dummy", hp, [move], lambda enemy, turn: move)


# --- policies --------------------------------------------------------------
# A policy is: given the engine and the player, return a card to play, or None
# to end the turn. That is the whole interface -- swap in a neural net later
# and nothing else changes.

def greedy(engine, player) -> Optional[Card]:
    """Block if the incoming hit would actually hurt, otherwise attack."""
    playable = engine.playable_cards(player)
    if not playable:
        return None
    incoming = sum(e.current_move.damage for e in engine.enemies_alive()
                   if e.current_move)
    threatened = incoming > player.block and player.hp <= incoming * 2
    wanted = "Defend" if threatened else "Strike"
    for card in playable:
        if card.name == wanted:
            return card
    return playable[0]          # only the other kind left -- play it anyway


def aggressive(engine, player) -> Optional[Card]:
    """Strike whenever possible; never block. A useful baseline to beat."""
    for card in engine.playable_cards(player):
        if card.name == "Strike":
            return card
    return None


def random_policy(engine, player) -> Optional[Card]:
    playable = engine.playable_cards(player)
    return player.rng.choice(playable) if playable else None


# --- the core battle function ----------------------------------------------

class Result(object):
    """What came out of one fight."""

    def __init__(self, won, turns, player_hp, enemy_hp, log):
        self.won = won
        self.turns = turns
        self.player_hp = player_hp
        self.enemy_hp = enemy_hp
        self.log = log

    def __repr__(self):
        return "<{} in {} turns, player {} hp>".format(
            "WON" if self.won else "LOST", self.turns, self.player_hp)


def battle(policy: Callable = greedy, seed: Optional[int] = None,
           player_hp: int = 30, energy: int = 3,
           enemy_hp: int = 75, enemy_damage: int = 11,
           max_turns: int = 50, verbose: bool = False) -> Result:
    """Run one fight to the end and return the result.

    This is the whole turn structure, and it is the same cycle play.py and
    env.py drive:

        start_player_turn()   draw 5, refill energy, clear block
        ... play cards ...    until the policy stops or nothing is playable
        end_player_turn()     discard the hand, end-of-turn effects
        run_enemy_turn()      the enemy acts

    `max_turns` is a safety cap, not a rule: a fight that hits it is a finding
    (a policy that never kills anything), not a normal outcome.

    THE DEFAULTS ARE TUNED, not arbitrary. The obvious numbers (50 hp vs a
    40 hp enemy hitting for 8) make every policy win 200/200 -- including a
    random one -- which is useless to train against: no gradient, nothing to
    learn, and no way to tell a good policy from a bad one. Measured over 150
    seeds per arm, these defaults give:

        aggressive (never blocks)     0%
        random                       61%
        greedy (blocks when hurt)    80%

    Blocking is now load-bearing, random is beatable, and there is headroom
    above the scripted baseline. Pass your own numbers to make it easier or
    harder -- `battle(greedy, player_hp=50, enemy_hp=40, enemy_damage=8)` is
    the trivial version if you just want to watch the loop run.
    """
    seed_content(seed)          # pins the enemy's HP roll; see entities.py
    player = Player("Hero", player_hp, energy, deck=make_deck())
    enemy = make_dummy(enemy_hp, enemy_damage)

    # scale_enemies=False keeps the dummy at exactly enemy_hp -- the
    # multiplayer scaling would otherwise inflate it.
    engine = CombatEngine([player], [enemy], seed=seed, scale_enemies=False)

    turns = 0
    engine.start_player_turn()
    while not engine.is_over and turns < max_turns:
        turns += 1
        if verbose:
            _show(engine, player, enemy, turns)

        # Play cards until the policy declines. Bounded, so a policy that
        # keeps returning an unplayable card cannot spin forever.
        for _ in range(20):
            card = policy(engine, player)
            if card is None:
                break
            if not engine.play_card(player, card, target=enemy):
                break       # engine refused it -- stop rather than retry
            if verbose:
                print("    plays {:<7} -> enemy {} hp, block {}".format(
                    card.name, enemy.hp, player.block))
            if engine.is_over:
                break

        if engine.is_over:
            break
        engine.end_player_turn()
        if not engine.is_over:
            engine.run_enemy_turn()
        if not engine.is_over:
            engine.start_player_turn()

    return Result(engine.victory, turns, player.hp, enemy.hp, engine.log)


def _show(engine, player, enemy, turn):
    hand = {}
    for c in player.hand:
        hand[c.name] = hand.get(c.name, 0) + 1
    print("  turn {:<2} you {}/{} hp, {} block, {} energy | "
          "Dummy {}/{} hp | hand {}".format(
              turn, player.hp, player.max_hp, player.block, player.energy,
              enemy.hp, enemy.max_hp,
              ", ".join("{}x{}".format(v, k) for k, v in sorted(hand.items()))))


# --- a tiny RL environment -------------------------------------------------
# The full CombatEnv is 181 actions and 817 observation floats. This is 3 and
# 7. Same engine underneath, so a policy that works here is solving a real
# (if small) slice of the game -- worth getting right before scaling up.

PLAY_STRIKE, PLAY_DEFEND, END_TURN = 0, 1, 2
ACTION_NAMES = ("strike", "defend", "end turn")


class SimpleEnv(object):
    """Gym-style env over the same battle. 3 actions, 7 observation floats.

        env = SimpleEnv(seed=0)
        obs = env.reset()
        obs, reward, done, info = env.step(action)

    Observation, all roughly 0-1:
        0 your hp        3 incoming damage next enemy turn
        1 your block     4 Strikes in hand
        2 enemy hp       5 Defends in hand
                         6 energy
    """

    def __init__(self, seed=None, player_hp=30, energy=3,
                 enemy_hp=75, enemy_damage=11, max_turns=50):
        self.seed = seed
        self.player_hp = player_hp
        self.energy = energy
        self.enemy_hp = enemy_hp
        self.enemy_damage = enemy_damage
        self.max_turns = max_turns
        self.engine = None

    def reset(self, seed=None):
        s = self.seed if seed is None else seed
        seed_content(s)
        self.player = Player("Hero", self.player_hp, self.energy, deck=make_deck())
        self.enemy = make_dummy(self.enemy_hp, self.enemy_damage)
        self.engine = CombatEngine([self.player], [self.enemy], seed=s,
                                   scale_enemies=False)
        self.engine.start_player_turn()
        return self._observe()

    def _hand_counts(self):
        strikes = sum(1 for c in self.player.hand if c.name == "Strike")
        defends = sum(1 for c in self.player.hand if c.name == "Defend")
        return strikes, defends

    def _observe(self):
        p, e = self.player, self.enemy
        strikes, defends = self._hand_counts()
        incoming = e.current_move.damage if (e.alive and e.current_move) else 0
        return [
            p.hp / max(1, p.max_hp),
            min(p.block, 20) / 20.0,
            e.hp / max(1, e.max_hp),
            incoming / 20.0,
            strikes / 5.0,
            defends / 5.0,
            p.energy / max(1, p.max_energy),
        ]

    def legal_actions(self):
        """END_TURN is always legal; the two card actions only when you hold
        that card AND can afford it. Same source of truth as the full env --
        the engine's own playable_cards."""
        legal = [False, False, True]
        if self.engine is None or self.engine.is_over:
            return legal
        for card in self.engine.playable_cards(self.player):
            if card.name == "Strike":
                legal[PLAY_STRIKE] = True
            elif card.name == "Defend":
                legal[PLAY_DEFEND] = True
        return legal

    def step(self, action):
        engine = self.engine
        if engine.is_over:
            return self._observe(), 0.0, True, {"absorbing": True}

        reward = 0.0
        if action == END_TURN:
            engine.end_player_turn()
            if not engine.is_over:
                engine.run_enemy_turn()
            if not engine.is_over:
                engine.start_player_turn()
        else:
            wanted = "Strike" if action == PLAY_STRIKE else "Defend"
            card = next((c for c in engine.playable_cards(self.player)
                         if c.name == wanted), None)
            if card is None:
                reward -= 1.0            # illegal: mask it and this never fires
            else:
                before = self.enemy.hp
                engine.play_card(self.player, card, target=self.enemy)
                reward += 0.1 * (before - self.enemy.hp)

        done = engine.is_over
        truncated = engine.turn_number > self.max_turns
        if done:
            reward += 10.0 if engine.victory else -10.0
        elif truncated:
            done = True
        return (self._observe(), reward, done,
                {"truncated": truncated, "turn": engine.turn_number})


# --- play it yourself ------------------------------------------------------
# The input plumbing is imported from play.py rather than rewritten: ask()
# turns Ctrl+C and Ctrl+D into a clean quit instead of a traceback, which took
# a real bug to get right (14 unguarded input() sites, only 2 of them
# guarded). Same reasoning as the engine -- do not keep a second copy.

SIMPLE_COMMANDS = (
    ("<#>", "play that card"), ("e", "end turn"), ("d", "draw pile"),
    ("p", "discard pile"), ("?", "help"), ("q", "quit"),
)


def _legend():
    print("  " + "   ".join("{}={}".format(k, v) for k, v in SIMPLE_COMMANDS))


def _render(engine, player, enemy):
    from play import hp_bar
    print()
    print("=" * 64)
    intent = "-"
    if enemy.alive and enemy.current_move:
        intent = "{} ({} dmg)".format(enemy.current_move.name,
                                      enemy.current_move.damage)
    print("  Dummy   {}   Intent: {}".format(
        hp_bar(enemy.hp, enemy.max_hp), intent))
    print("  You     {}   Block {}   Energy {}/{}".format(
        hp_bar(player.hp, player.max_hp), player.block,
        player.energy, player.max_energy))
    print()
    if not player.hand:
        print("  Hand: (empty)")
        return
    print("  Hand:")
    playable = {id(c) for c in engine.playable_cards(player)}
    for i, card in enumerate(player.hand):
        mark = " " if id(card) in playable else "x"
        print("  {} {}: [{}] {:<7} {}".format(
            mark, i, card.current_cost(player), card.name, card.description))


def _show_pile(cards, label):
    if not cards:
        print("  {}: (empty)".format(label))
        return
    counts = {}
    for c in cards:
        counts[c.name] = counts.get(c.name, 0) + 1
    print("  {} ({} cards): {}".format(
        label, len(cards),
        ", ".join("{}x {}".format(v, k) for k, v in sorted(counts.items()))))


def play_interactive(seed: Optional[int] = None, player_hp: int = 30,
                     energy: int = 3, enemy_hp: int = 75,
                     enemy_damage: int = 11, max_turns: int = 50):
    """Play one fight yourself, in the terminal.

    Same engine, same cards, same turn cycle as battle() -- this only swaps
    the policy function for a person at a keyboard."""
    from play import QuitGame, ask

    seed_content(seed)
    player = Player("You", player_hp, energy, deck=make_deck())
    enemy = make_dummy(enemy_hp, enemy_damage)
    engine = CombatEngine([player], [enemy], seed=seed, scale_enemies=False)

    print()
    print("Strike deals 6. Defend gains 5 Block. The Dummy hits for {} every"
          " turn.".format(enemy_damage))
    print("Block is spent absorbing damage and is gone at the start of your"
          " next turn.")
    _legend()

    engine.start_player_turn()
    turns = 0

    try:
        while not engine.is_over and turns < max_turns:
            turns += 1
            _render(engine, player, enemy)

            while True:                       # one turn's worth of actions
                if engine.is_over:
                    break
                choice = ask("  You> ").lower()
                if choice in ("q", "quit"):
                    raise QuitGame()
                if choice in ("?", "h", "help"):
                    _legend()
                    continue
                if choice == "d":
                    _show_pile(player.draw_pile, "Draw pile")
                    continue
                if choice == "p":
                    _show_pile(player.discard_pile, "Discard pile")
                    continue
                if choice in ("e", ""):
                    break
                if not choice.isdigit() or int(choice) >= len(player.hand):
                    print("  no such card -- pick a number from your hand,"
                          " or 'e' to end the turn")
                    continue

                card = player.hand[int(choice)]
                # The engine's own answer, not a second opinion. If it says
                # no, it says WHY -- same string play.py and the RL mask use.
                refusal = engine.why_not_playable(player, card)
                if refusal is not None:
                    print("  can't: {}".format(refusal))
                    continue
                engine.play_card(player, card, target=enemy)
                _render(engine, player, enemy)

            if engine.is_over:
                break

            # Marked HERE, not at the top of the turn: your own card plays are
            # already rendered live as you make them, so replaying them would
            # just be noise. Everything after this point is the enemy phase.
            log_seen = len(engine.log)
            engine.end_player_turn()
            if not engine.is_over:
                engine.run_enemy_turn()
            print()
            for line in engine.log[log_seen:]:
                print("    {}".format(line))
            if not engine.is_over:
                engine.start_player_turn()

    except QuitGame:
        print("\n  (quit)")
        return None

    print()
    print("=" * 64)
    if engine.victory:
        print("  YOU WIN -- {} hp left, {} turns".format(player.hp, turns))
    elif turns >= max_turns:
        print("  Out of turns after {} -- the Dummy outlasted you.".format(turns))
    else:
        print("  YOU DIED -- the Dummy had {} hp left.".format(enemy.hp))
    print("=" * 64)
    return Result(engine.victory, turns, player.hp, enemy.hp, engine.log)


# --- demo ------------------------------------------------------------------

def _demo():
    print("=" * 62)
    print("ONE FIGHT, greedy policy")
    print("=" * 62)
    result = battle(greedy, seed=0, verbose=True)
    print("\n  ->", result)

    print()
    print("=" * 62)
    print("200 FIGHTS PER POLICY")
    print("=" * 62)
    for name, policy in (("aggressive", aggressive), ("greedy", greedy),
                         ("random", random_policy)):
        results = [battle(policy, seed=s) for s in range(200)]
        wins = sum(r.won for r in results)
        hp = sum(r.player_hp for r in results) / len(results)
        turns = sum(r.turns for r in results) / len(results)
        print("  {:<11} {:>3}/200 won   avg {:>5.1f} hp left   avg {:.1f} turns"
              .format(name, wins, hp, turns))

    print()
    print("=" * 62)
    print("SimpleEnv: 3 actions, 7 observation floats")
    print("=" * 62)
    env = SimpleEnv(seed=0)
    obs = env.reset()
    print("  obs      {}".format([round(x, 2) for x in obs]))
    print("  legal    {}".format(
        [n for n, ok in zip(ACTION_NAMES, env.legal_actions()) if ok]))
    total, done, steps = 0.0, False, 0
    while not done and steps < 500:
        steps += 1
        legal = env.legal_actions()
        action = PLAY_STRIKE if legal[PLAY_STRIKE] else END_TURN
        obs, reward, done, info = env.step(action)
        total += reward
    print("  a strike-first policy: return {:+.1f} over {} steps, won={}"
          .format(total, steps, env.engine.victory))


if __name__ == "__main__":
    import sys as _sys
    if "demo" in _sys.argv:
        _demo()
    else:
        play_interactive()
