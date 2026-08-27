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

    from testing.simple import battle, greedy
    result = battle(greedy, seed=0, verbose=True)
"""

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


from typing import Callable, List, Optional

from game_engine.cards import Card, CardType, TargetMode, fx_strike, fx_defend
from game_engine.combat import CombatEngine
from game_engine.enemies import Enemy, IntentType, Move
from game_engine.entities import Player, seed_content

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

def make_party(count: int = 1, hp: int = 30, energy: int = 3) -> List[Player]:
    """`count` identical heroes, each with a Strike/Defend deck.

    Identical on purpose: in the cut-down game the interesting co-op question
    is who spends their energy blocking versus attacking, not who brought the
    better deck. Give them different decks and you cannot tell which effect
    you are looking at."""
    if not 1 <= count <= 4:
        raise ValueError("the engine supports 1-4 players, got {}".format(count))
    return [Player("Hero" if count == 1 else "Hero {}".format(i + 1),
                   hp, energy, deck=make_deck())
            for i in range(count)]


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
    """What came out of one fight.

    `party_hp` is a list, one entry per hero, so a co-op result is not
    squeezed into a single number. `player_hp` stays as the FIRST hero's HP
    so solo callers written before co-op existed keep working."""

    def __init__(self, won, turns, party_hp, enemy_hp, log):
        self.won = won
        self.turns = turns
        self.party_hp = list(party_hp)
        self.player_hp = self.party_hp[0]
        self.enemy_hp = enemy_hp
        self.log = log

    def __repr__(self):
        who = (str(self.player_hp) if len(self.party_hp) == 1
               else "/".join(str(h) for h in self.party_hp))
        return "<{} in {} turns, party {} hp>".format(
            "WON" if self.won else "LOST", self.turns, who)


def battle(policy: Callable = greedy, seed: Optional[int] = None,
           player_hp: int = 30, energy: int = 3,
           enemy_hp: int = 75, enemy_damage: int = 11,
           max_turns: int = 50, verbose: bool = False,
           players: int = 1, scale_enemy: Optional[bool] = None) -> Result:
    """Run one fight to the end and return the result.

    CO-OP: `players` is 1-4. Every living hero acts in seat order each turn,
    each driven by the same `policy` -- which needs no change, because a
    policy has always been `(engine, player) -> card`, and it is handed
    whichever player is currently acting.

    `scale_enemy` defaults to None = "on when there is more than one hero",
    because without it co-op is a walkover: the dummy hits ONE target, so
    incoming damage per hero falls as 1/n while party HP grows as n. Pass
    True/False to force it.

    CO-OP IS NOT TUNED THE WAY SOLO IS, and it would be dishonest to imply
    otherwise. Solo's numbers were swept until the policies separated; co-op
    has a much narrower band and the ordering does not survive it. Measured
    over 80 seeds per arm, with HP scaling on:

        players  enemy dmg   aggressive   greedy   random
           2         11          10%        100%     100%
           2         13          10%         80%      80%   <- a real spread
           3         16           0%         26%      75%   <- greedy INVERTS
           4         22          56%          0%      21%   <- so does the order

    That inversion is a real finding, not noise: against a big scaled enemy
    the fight outlasts `max_turns`, so turtling loses to the clock and racing
    wins. `greedy` stops being the right baseline somewhere around 3 players.
    If you want a learnable co-op task, tune `enemy_hp`/`enemy_damage` for
    your party size -- config.json's `simple` section exists for exactly that.

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
    if scale_enemy is None:
        scale_enemy = players > 1
    seed_content(seed)          # pins the enemy's HP roll; see entities.py
    party = make_party(players, player_hp, energy)
    enemy = make_dummy(enemy_hp, enemy_damage)

    engine = CombatEngine(party, [enemy], seed=seed, scale_enemies=scale_enemy)

    turns = 0
    engine.start_player_turn()
    while not engine.is_over and turns < max_turns:
        turns += 1
        if verbose:
            _show(engine, party, enemy, turns)

        # Each living hero takes their sub-turn in seat order. A downed one is
        # skipped rather than ending the fight -- the engine only calls defeat
        # once EVERY player is down, so a survivor can still finish the job.
        for player in engine.players:
            if not player.alive or engine.is_over:
                continue
            # Play cards until the policy declines. Bounded, so a policy that
            # keeps returning an unplayable card cannot spin forever.
            for _ in range(20):
                card = policy(engine, player)
                if card is None:
                    break
                if not engine.play_card(player, card, target=enemy):
                    break       # engine refused it -- stop rather than retry
                if verbose:
                    print("    {} plays {:<7} -> enemy {} hp, block {}".format(
                        player.name, card.name, enemy.hp, player.block))
                if engine.is_over:
                    break

        if engine.is_over:
            break
        engine.end_player_turn()
        if not engine.is_over:
            engine.run_enemy_turn()
        if not engine.is_over:
            engine.start_player_turn()

    return Result(engine.victory, turns,
                  [p.hp for p in engine.players], enemy.hp, engine.log)


def _show(engine, party, enemy, turn):
    print("  turn {:<2} Dummy {}/{} hp".format(turn, enemy.hp, enemy.max_hp))
    for player in party:
        hand = {}
        for c in player.hand:
            hand[c.name] = hand.get(c.name, 0) + 1
        print("      {:<7} {}/{} hp, {} block, {} energy | hand {}".format(
            player.name, player.hp, player.max_hp, player.block, player.energy,
            ", ".join("{}x{}".format(v, k) for k, v in sorted(hand.items()))
            or "(empty)"))


# --- a tiny RL environment -------------------------------------------------
# The full CombatEnv is 181 actions and 817 observation floats. This is 3 and
# 7. Same engine underneath, so a policy that works here is solving a real
# (if small) slice of the game -- worth getting right before scaling up.

PLAY_STRIKE, PLAY_DEFEND, END_TURN = 0, 1, 2
ACTION_NAMES = ("strike", "defend", "end turn")


class SimpleEnv(object):
    """Gym-style env over the same battle. 3 actions; 7 observation floats
    solo, plus 2 per teammate in co-op.

        env = SimpleEnv(seed=0)              # solo: 7 floats
        env = SimpleEnv(players=3, seed=0)   # co-op: 7 + 2x2 = 11 floats
        obs = env.reset()
        obs, reward, done, info = env.step(action)

    Observation, all roughly 0-1:
        0 your hp        3 incoming damage next enemy turn
        1 your block     4 Strikes in hand
        2 enemy hp       5 Defends in hand
                         6 energy
        then per teammate, in the order described below:
        +0 their hp      +1 their block

    EGOCENTRIC, exactly like the full CombatEnv: slot 0 is whoever is acting
    right now, and teammates follow in wrapped seat order. A single shared
    policy can therefore read its OWN hp at a fixed place -- which is the
    whole reason the big env was rotated too.

    SOLO IS UNCHANGED AT 7 FLOATS, deliberately. A saved agent trained before
    co-op existed still loads and runs. Ask for players>1 and the observation
    grows; ask the env for its size rather than hardcoding 7.

    CO-OP TURN ORDER mirrors CombatEnv: heroes act one at a time in sequence,
    END_TURN passes to the next, and the enemy acts only once everyone has
    had their sub-turn.
    """

    def __init__(self, seed=None, player_hp=30, energy=3,
                 enemy_hp=75, enemy_damage=11, max_turns=50,
                 players=1, scale_enemy=None):
        if not 1 <= players <= 4:
            raise ValueError("players must be 1-4, got {}".format(players))
        self.seed = seed
        self.player_hp = player_hp
        self.energy = energy
        self.enemy_hp = enemy_hp
        self.enemy_damage = enemy_damage
        self.max_turns = max_turns
        self.n_players = players
        # None = on when there is more than one hero; see battle().
        self.scale_enemy = (players > 1) if scale_enemy is None else scale_enemy
        self.active_idx = 0
        self.engine = None

    def observation_size(self):
        """7 for solo, +2 per teammate. Read this instead of hardcoding a
        number -- the trainer does."""
        return 7 + 2 * (self.n_players - 1)

    def reset(self, seed=None):
        s = self.seed if seed is None else seed
        seed_content(s)
        party = make_party(self.n_players, self.player_hp, self.energy)
        self.enemy = make_dummy(self.enemy_hp, self.enemy_damage)
        self.engine = CombatEngine(party, [self.enemy], seed=s,
                                   scale_enemies=self.scale_enemy)
        self.engine.start_player_turn()
        self.active_idx = 0
        return self._observe()

    # ---- whose turn is it ----
    @property
    def player(self):
        """The acting hero. Named `player` so every solo caller written
        before co-op keeps working unchanged."""
        if self.engine is None:
            return None
        idx = min(self.active_idx, len(self.engine.players) - 1)
        return self.engine.players[idx]

    def _obs_order(self):
        """Acting hero first, the rest in wrapped seat order."""
        players = self.engine.players
        idx = self.active_idx if self.active_idx < len(players) else 0
        return players[idx:] + players[:idx]

    def _advance(self):
        """Hand the sub-turn to the next hero; resolve the round after the
        last one. Mirrors CombatEnv._advance_sub_turn."""
        engine = self.engine
        self.active_idx += 1
        if self.active_idx >= len(engine.players):
            engine.end_player_turn()
            if not engine.is_over:
                engine.run_enemy_turn()
            if not engine.is_over:
                engine.start_player_turn()
            self.active_idx = 0

    def _hand_counts(self, player):
        strikes = sum(1 for c in player.hand if c.name == "Strike")
        defends = sum(1 for c in player.hand if c.name == "Defend")
        return strikes, defends

    def _observe(self):
        order = self._obs_order()
        me, e = order[0], self.enemy
        strikes, defends = self._hand_counts(me)
        incoming = e.current_move.damage if (e.alive and e.current_move) else 0
        obs = [
            me.hp / max(1, me.max_hp),
            min(me.block, 20) / 20.0,
            e.hp / max(1, e.max_hp),
            incoming / 20.0,
            strikes / 5.0,
            defends / 5.0,
            me.energy / max(1, me.max_energy),
        ]
        # Teammates: hp and block only. Enough to answer "does anyone need me
        # to tank for them", without doubling the vector.
        for mate in order[1:]:
            obs.append(mate.hp / max(1, mate.max_hp))
            obs.append(min(mate.block, 20) / 20.0)
        return obs

    def legal_actions(self):
        """END_TURN is always legal; the two card actions only when the
        ACTING hero holds that card and can afford it. Same source of truth
        as the full env -- the engine's own playable_cards."""
        legal = [False, False, True]
        if self.engine is None or self.engine.is_over:
            return legal
        me = self.player
        if me is None or not me.alive:
            return legal
        for card in self.engine.playable_cards(me):
            if card.name == "Strike":
                legal[PLAY_STRIKE] = True
            elif card.name == "Defend":
                legal[PLAY_DEFEND] = True
        return legal

    def step(self, action):
        engine = self.engine
        if engine.is_over:
            return self._observe(), 0.0, True, {"absorbing": True}

        me = self.player
        reward = 0.0
        if action == END_TURN or me is None or not me.alive:
            self._advance()
        else:
            wanted = "Strike" if action == PLAY_STRIKE else "Defend"
            card = next((c for c in engine.playable_cards(me)
                         if c.name == wanted), None)
            if card is None:
                reward -= 1.0            # illegal: mask it and this never fires
            else:
                before = self.enemy.hp
                engine.play_card(me, card, target=self.enemy)
                reward += 0.1 * (before - self.enemy.hp)

        done = engine.is_over
        truncated = engine.turn_number > self.max_turns
        if done:
            reward += 10.0 if engine.victory else -10.0
        elif truncated:
            done = True
        return (self._observe(), reward, done,
                {"truncated": truncated, "turn": engine.turn_number,
                 "acting": self.active_idx})


# --- play it yourself ------------------------------------------------------
# The input plumbing is imported from play.py rather than rewritten: ask()
# turns Ctrl+C and Ctrl+D into a clean quit instead of a traceback, which took
# a real bug to get right (14 unguarded input() sites, only 2 of them
# guarded). Same reasoning as the engine -- do not keep a second copy.

SIMPLE_COMMANDS = (
    ("<#>", "play that card"), ("e", "end turn"), ("n", "next hero"),
    ("s", "switch hero"), ("a", "all hands"),
    ("d", "draw pile"), ("p", "discard pile"), ("?", "help"), ("q", "quit"),
)

# Only meaningful with a party. Solo hides them rather than offering keys
# that answer "there is nobody else".
COOP_ONLY = ("n", "s", "a")


def _legend(solo=True):
    items = [(k, v) for k, v in SIMPLE_COMMANDS
             if not solo or k not in COOP_ONLY]
    print("  " + "   ".join("{}={}".format(k, v) for k, v in items))


def _render(engine, player, enemy):
    from testing.play import hp_bar
    print()
    print("=" * 64)
    intent = "-"
    if enemy.alive and enemy.current_move:
        intent = "{} ({} dmg)".format(enemy.current_move.name,
                                      enemy.current_move.damage)
    print("  Dummy   {}   Intent: {}".format(
        hp_bar(enemy.hp, enemy.max_hp), intent))
    # Every hero, with "->" marking whose turn it is. In solo there is only
    # one line and the marker is harmless.
    for member in engine.players:
        mark = "->" if member is player else "  "
        state = "" if member.alive else "   (down)"
        print("{} {:<7} {}   Block {}   Energy {}/{}{}".format(
            mark, member.name, hp_bar(member.hp, member.max_hp), member.block,
            member.energy, member.max_energy, state))
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


def _show_all_hands(engine, active):
    """Every hero's hand at once, so you can plan the round before spending.

    Cards are listed with the index you would type AFTER switching to that
    hero -- indices are per-hand, not global, exactly as _render() shows
    them. 'x' marks a card that hero cannot currently afford, asked of the
    engine per hero because each has their own energy.
    """
    from testing.play import hp_bar
    print()
    print("  All hands:")
    for member in engine.players:
        mark = "->" if member is active else "  "
        if not member.alive:
            print("{} {:<7} (down)".format(mark, member.name))
            continue
        print("{} {:<7} {}   Block {}   Energy {}/{}".format(
            mark, member.name, hp_bar(member.hp, member.max_hp), member.block,
            member.energy, member.max_energy))
        if not member.hand:
            print("       (empty hand)")
            continue
        playable = {id(c) for c in engine.playable_cards(member)}
        print("       " + "   ".join(
            "{}{}:[{}] {}".format("" if id(c) in playable else "x",
                                  i, c.current_cost(member), c.name)
            for i, c in enumerate(member.hand)))


def _pick_hero(engine, active, arg, ask, QuitGame):
    """Resolve 's' / 's2' to a seat index, or None if the pick was no good.

    Accepts the number inline ('s2') so the common case is one keystroke
    pair, and falls back to a prompt for a bare 's'. Numbering shown to the
    player is 1-based to match the "Hero 2" labels; the return is 0-based.
    """
    living = [i for i, m in enumerate(engine.players) if m.alive]
    if not arg:
        print("  " + "   ".join(
            "{}={}".format(i + 1, engine.players[i].name) for i in living))
        arg = ask("  switch to which hero? ").strip()
        if arg.lower() in ("q", "quit"):
            raise QuitGame()
    if not arg.isdigit():
        print("  not a hero number -- try 's2', or 's' on its own for a list")
        return None
    idx = int(arg) - 1
    if idx not in living:
        print("  no hero {} to switch to (living: {})".format(
            arg, ", ".join(str(i + 1) for i in living)))
        return None
    if engine.players[idx] is active:
        print("  {} is already acting".format(engine.players[idx].name))
        return None
    return idx


def _take_sub_turn(engine, player, enemy, ask, QuitGame):
    """One hero's sub-turn at the keyboard.

    Returns who should act next:
      "end"  -- end the whole ROUND ('e'); the enemy phase runs
      "next" -- pass to the next hero in seat order ('n')
      <int>  -- a seat index the player jumped to explicitly ('s2')

    Solo only ever sees "end" -- with one hero the next sub-turn is the next
    round, so 'n'/'s' are not offered at all."""
    solo = len(engine.players) == 1
    prompt = "  {}> ".format(player.name)
    while True:
        if engine.is_over:
            return "end"
        choice = ask(prompt).lower()
        if choice in ("q", "quit"):
            raise QuitGame()
        if choice in ("?", "h", "help"):
            _legend(solo)
            continue
        if choice == "d":
            _show_pile(player.draw_pile, "Draw pile")
            continue
        if choice == "p":
            _show_pile(player.discard_pile, "Discard pile")
            continue
        if choice == "a" and not solo:
            _show_all_hands(engine, player)
            continue
        if choice.startswith("s") and not solo:
            picked = _pick_hero(engine, player, choice[1:].strip(),
                                ask, QuitGame)
            if picked is None:
                continue
            return picked                 # jump straight to that hero
        if choice == "n" and not solo:
            return "next"                 # pass to the next hero
        if choice in ("e", ""):
            return "end"                  # end the round for everyone
        if not choice.isdigit() or int(choice) >= len(player.hand):
            print("  no such card -- pick a number from {}'s hand, "
                  "'e' to end the turn{}".format(
                      player.name,
                      "" if solo else ", 'n' for the next hero, 's2' to jump"))
            continue

        card = player.hand[int(choice)]
        # The engine's own answer, not a second opinion. If it says no, it
        # says WHY -- same string play.py and the RL mask use.
        refusal = engine.why_not_playable(player, card)
        if refusal is not None:
            print("  can't: {}".format(refusal))
            continue
        engine.play_card(player, card, target=enemy)
        _render(engine, player, enemy)


def play_interactive(seed: Optional[int] = None, player_hp: int = 30,
                     energy: int = 3, enemy_hp: int = 75,
                     enemy_damage: int = 11, max_turns: int = 50,
                     players: int = 1, scale_enemy: Optional[bool] = None):
    """Play one fight yourself, in the terminal.

    Same engine, same cards, same turn cycle as battle() -- this only swaps
    the policy function for a person at a keyboard.

    CO-OP: with players>1 each hero takes a sub-turn in seat order, and the
    header marks whose it is with "->". Type `n` to pass to the next hero
    without ending the whole party's turn -- `e` still ends the round for
    everyone, which is the distinction play.py's "Whose turn?" menu makes
    too.

    Seat order is only the default. `s2` jumps straight to Hero 2 and can go
    backwards, so you can open with the hero whose hand you have seen -- `a`
    shows every hand at once for exactly that. This is play.py's free-pick
    model; `n` is kept as the one-key shorthand for the common case."""
    from testing.play import QuitGame, ask

    if scale_enemy is None:
        scale_enemy = players > 1
    seed_content(seed)
    party = make_party(players, player_hp, energy)
    for i, member in enumerate(party):
        member.name = "You" if players == 1 else "Hero {}".format(i + 1)
    enemy = make_dummy(enemy_hp, enemy_damage)
    engine = CombatEngine(party, [enemy], seed=seed, scale_enemies=scale_enemy)

    print()
    who = "You" if players == 1 else "{} heroes".format(players)
    print("{} vs the Dummy ({} hp, hits one target for {} every turn)."
          .format(who, enemy.max_hp, enemy_damage))
    print("Strike deals 6. Defend gains 5 Block.")
    print("Block is spent absorbing damage and is gone at the start of your"
          " next turn.")
    _legend(solo=(players == 1))

    engine.start_player_turn()
    turns = 0

    try:
        while not engine.is_over and turns < max_turns:
            turns += 1
            # Heroes act in seat order by default, but 's<N>' can jump to any
            # living one, so this walks an index instead of a for-loop.
            # Falling off the end still ends the round, which is exactly what
            # 'n' on the last hero has always done.
            active = 0
            while active < len(engine.players) and not engine.is_over:
                player = engine.players[active]
                if not player.alive:
                    active += 1
                    continue
                _render(engine, player, enemy)
                nxt = _take_sub_turn(engine, player, enemy, ask, QuitGame)
                if nxt == "end":
                    break                     # 'e' ends the round for everyone
                active = active + 1 if nxt == "next" else nxt
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
        survivors = "/".join(str(m.hp) for m in engine.players)
        print("  YOU WIN -- {} hp left, {} turns".format(survivors, turns))
    elif turns >= max_turns:
        print("  Out of turns after {} -- the Dummy outlasted you.".format(turns))
    else:
        print("  YOU DIED -- the Dummy had {} hp left.".format(enemy.hp))
    print("=" * 64)
    return Result(engine.victory, turns,
                  [m.hp for m in engine.players], enemy.hp, engine.log)


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
    # Setup comes from config.json's `simple` section, so a UI can point this
    # at a party size and enemy without editing code. Missing file or missing
    # section -> the solo defaults, exactly as before configs existed.
    from testing import config as _config

    _argv = [a for a in _sys.argv[1:] if not a.startswith("-")]
    _demo_mode = "demo" in _argv
    _path = next((a for a in _argv if a.endswith(".json")), None)
    try:
        _cfg = _config.load(_path, quiet=True)
    except _config.ConfigError as _exc:
        print("Config error: {}".format(_exc))
        _sys.exit(2)
    _kw = _config.simple_kwargs(_cfg)
    if _cfg.get("seed") is not None:
        _kw["seed"] = _cfg["seed"]

    if _demo_mode:
        _demo()
    else:
        play_interactive(**_kw)