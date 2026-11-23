"""A person plays next to the agent, on a page in their browser, without knowing which version it is, and rates each fight.

    python playtest.py --name Sam                play a session
    python playtest.py --name Sam --resume       carry on from where Sam stopped, even mid-fight
    python playtest.py --name Sam --carry-on     carry on if Sam has an unfinished session, otherwise start a new one
    python playtest.py --name Sam --terminal     play by typing, without the page
    python playtest.py --report                  summarise every session in runs/playtest

The page (playtest_ui.py, playtest_ui.html) sends the same answers a person would type, so nothing else depends on which is used.

The person plays seat 1 and the agent seat 0. With --players 3 (the default) a scripted teammate sits in seat 2, as
in the simulated tests, with its tie-break fixed so it doesn't favour the agent's seat (see Table._play).

Each version plays the same fights: the session is a set of blocks, one lineup, starting HP and seed per block. The blocks
climb LADDER (an easy fight, then an elite, then a boss), the versions' order inside each block is a rotation of one random
order, so across three blocks every version plays first, second and third once, and after each block the player picks the
partner they liked most in it. (Sessions from before LAYOUT keep their own layout: elites or bosses, an order drawn per block and
one pick at the end.) The player only ever sees "Partner". Nothing is changed in the
agent's input or the engine: a Wait by the agent lets the person take one action, as it does a scripted teammate.
The person is asked first every round, and plays until they hand over with w (Table.person_opens): the real game's turns
are simultaneous, so nothing there stops a player going ahead of the agent. Versions may add play-time rules (agent_move).
Everything goes to runs/playtest/<name>_<time>.jsonl as it happens: each answer, and each fight when it's rated. A session is
fixed by its seed and its answers, so --resume plays the answers again out of sight (class Saved) and nothing is lost by stopping.
"""
import argparse
import dataclasses
import glob
import io
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join("runs", "playtest")
VERSIONS = {"best": ("runs/pair_survive_1m_s1/final_model.zip", ()),
            "best_timing": ("runs/pair_survive_1m_s1/final_model.zip", ("timing",)),
            "best_rules": ("runs/pair_survive_1m_s1/final_model.zip", ("timing", "defend")),
            "best_paced": ("runs/pair_survive_1m_s1/final_model.zip", ("paced",)),
            "best_paced_rules": ("runs/pair_survive_1m_s1/final_model.zip", ("paced", "timing", "defend", "rally", "gifts", "intangible", "beaten", "cover")),
            "old": ("runs/goal_control_s1/final_model.zip", ())}
TABLE = "you_first"                               # sessions from before this table are left out of the report
# Deck presets: how many cards of each kind every player gets. The cards come from the deck the agent was trained with (its config's
# real_deck), as many copies as that deck holds, so a Strike is likelier than an Uppercut and the agent never meets a card it hasn't seen.
DECK_PRESETS = {"Default": dict(block=4, attack=5, skill=3, power=2),
                "Small": dict(block=2, attack=3, skill=1, power=1),
                "Bloated": dict(block=7, attack=10, skill=5, power=4),
                "Helper": dict(block=4, attack=5, skill=3, power=2, helper=3)}
# Cards the whole team holds at most one copy of, and how often it keeps that one when the deal gave it any. Beacon of Hope doesn't
# stack (a second copy does nothing, in the engine and in the game), and a playtest partner with three replayed it. Extra copies become
# another card of the same kind. Only the playtest's dealing does this; the training's (real_engine) doesn't.
TEAM_LIMIT = {"beacon_of_hope": 0.5}
LEVELS =(1.0, 1.0, .75, .5, .25)                 # starting HP as a share of max, drawn per player, as in the tests
# How hard each block's fight is, block by block (block b is LADDER[b % 3]), and the enemy pools they draw from.
LADDER = ("easy", "elite", "boss")
LADDER_POOLS = {"easy": "HALLWAY", "elite": "ELITES", "boss": "BOSSES"}
LAYOUT = "ladder"                                 # the session layout above; sessions without it in their first row keep the earlier one
QUESTIONS = (("own_way", "I could play the way I wanted."),
             ("covered", "My partner covered me when I was in trouble."),
             ("predictable", "I could tell what my partner was going to do."),
             ("room", "My partner left me room to set up my plays."),
             ("sensible", "My partner's plays made sense. It didn't waste its cards."),
             ("mattered", "My own plays mattered to how the fight went."),
             ("again", "I would be happy to play with this partner again."))
HELP = """
  How to play
    3        play card 3 from your hand (it asks for a target if it needs one)
    3a       play card 3 on enemy a        3p  on Partner        3t  on your other teammate
    w        wait: let the others move
    e        end your turn
    l        look at the table again
    p        pause
    q        stop for now (your place is saved, so you can carry on later)
  You can go first every round: play what you like, then type w to let the others move. You'll get another move after them.
  The enemies attack once every player has ended their turn.
  Enemy attacks hit every player. Block only lasts until your next turn.
"""
LAST_OPTIONS = []                                 # the valid answers to the current prompt, for the automated check


class QuitSession(Exception):
    """The player asked to stop, or the input ended. undo: how many of the last answers only said so, which coming back shouldn't repeat."""

    def __init__(self, undo=0):
        super().__init__()
        self.undo = undo


class Saved:
    """Every answer the player gives, kept as they give it. A session is fixed by its seed and its answers, so coming back plays the answers again
    out of sight and the game is exactly where they left it. Also the player's clock: their time at a prompt, with pauses left out."""

    def __init__(self, write=None, todo=(), name="", welcome=""):
        self.write, self.name, self.welcome = write, name, welcome
        self.todo = list(todo)                    # answers to play back, oldest first
        self.count = 0                            # answers given so far
        self.seconds = 0.0
        self.screen = None                        # the real screen, while playing back

    def keep(self, prompt, text, seconds, stopped=False):
        self.count += 1
        self.seconds += seconds
        if self.write is not None:
            row = dict(kind="answer", prompt=prompt, options=LAST_OPTIONS, text=text, seconds=seconds)
            self.write(dict(row, stopped=True) if stopped else row)

    def hide_screen(self):
        if self.todo:
            self.screen, sys.stdout = sys.stdout, io.StringIO()

    def show_screen(self, say_where=True):
        """Back to the real screen, with what came after the last answer played back: where the player stopped."""
        if self.screen is not None:
            text = sys.stdout.getvalue()
            sys.stdout, self.screen = self.screen, None
            if say_where:
                announce(self.welcome)
                print(text, end="")

    def play_back(self, prompt):
        row = self.todo.pop(0)
        if (row["prompt"], row["options"]) != (prompt, LAST_OPTIONS):
            self.show_screen(say_where=False)
            raise SystemExit("This session's saved answers don't fit the game any more, so it can't carry on from where it stopped. "
                             "Its finished fights are safe. Please start a new session.")
        self.count += 1
        self.seconds += row["seconds"]
        sys.stdout.seek(0)
        sys.stdout.truncate()
        if UI is not None:
            UI.clear_notice()
        if row.get("stopped"):
            raise QuitSession
        return row["text"]


SAVE = Saved()
UI = None                                         # the browser page, unless playing in the terminal


def announce(text):
    """Something for the player to stop and read: a message on the page, a plain line in the terminal."""
    if UI is None:
        print(text)
    else:
        UI.notice(text.strip())


def carry_on_line():
    return UI.state["resume"] if UI is not None else f"python playtest.py --name {SAVE.name} --resume"


def pause(prompt):
    try:
        if UI is None:
            print(f"\n  Paused. Your place is saved. Press Enter when you're back, or close this window and carry on later with:\n    {carry_on_line()}")
            input("  ")
        else:
            UI.notice(f"Your place is saved. Come back when you're ready, or close this page and the game's window and carry on later with:\n{carry_on_line()}")
            UI.read("Paused", ["go"], {"go": "Carry on"})
    except (EOFError, KeyboardInterrupt):
        SAVE.keep(prompt, "", 0.0, stopped=True)
        raise QuitSession(undo=1) from None


def ask(prompt, options=None, labels=None):
    global LAST_OPTIONS
    LAST_OPTIONS = list(options or [])
    if SAVE.todo:
        return SAVE.play_back(prompt)
    SAVE.show_screen()
    while True:
        t0 = time.time()
        try:
            raw = UI.read(prompt, LAST_OPTIONS, labels) if UI is not None else input(prompt)
            raw = raw.lstrip("\ufeff\u00ef\u00bb\u00bf").strip()     # some piped input starts with a byte-order mark
        except (EOFError, KeyboardInterrupt):
            SAVE.keep(prompt, "", time.time() - t0, stopped=True)
            raise QuitSession(undo=1) from None
        if options and raw.lower() in ("p", "pause") and raw.lower() not in LAST_OPTIONS:      # p can also mean Partner, when it's asked which player
            pause(prompt)
            continue
        SAVE.keep(prompt, raw, time.time() - t0)
        return raw


def yes(prompt):
    while True:
        a = ask(prompt + " (y/n) ", ["y", "n"], {"y": "Yes", "n": "No"}).lower()
        if a in ("y", "yes"):
            return True
        if a in ("n", "no"):
            return False


def real_danger(rc, seat):
    """HP a player would lose in the coming enemy turn, through their Block, following Intercept (Combat._intercept)."""
    ally = rc.allies[seat]
    if not ally.is_alive():
        return 0

    def cover_of(victim):
        for other in rc.allies:
            st = other.get_status("intercepting") if other is not victim and other.is_alive() else None
            if st is not None and st.amount > 0 and victim in st.covered:
                return other
        return None

    taken = sum(rc.incoming(s) for s, v in enumerate(rc.allies) if v.is_alive() and cover_of(v) is ally)
    if cover_of(ally) is None:
        taken += rc.incoming(seat)
    return max(0, taken - ally.block)


def card_kinds(R, cards):
    """A deck's cards by kind, every copy kept: block (a skill that gives Block), skill (one that doesn't), attack, power, and helper
    (aimed at a teammate or every player: Block or a buff for them). A helper card is also a block or skill card."""
    kinds = defaultdict(list)
    for card in cards:
        s = R._static(card)
        if s.type in ("attack", "power"):
            kinds[s.type].append(card)
        elif s.type == "skill":
            kinds["block" if s.blocks else "skill"].append(card)
        if s.target in ("single_ally", "all_ally"):
            kinds["helper"].append(card)
    return kinds


def deal_decks(dice, R, cards, preset, players):
    """One deck per player from a preset, each card drawn at random from that kind of card in `cards`, then TEAM_LIMIT applied."""
    kinds = card_kinds(R, cards)
    decks = [[str(c) for kind, n in DECK_PRESETS[preset].items() for c in dice.choice(kinds[kind], size=n)] for _ in range(players)]
    return limit_team_cards(dice, decks, kinds)


def limit_team_cards(dice, decks, kinds):
    """At most one copy of each TEAM_LIMIT card in the whole team: with its chance one copy stays, on a random player who was dealt
    it, and every other copy becomes another card of the same kind. The deal is drawn first, so no other card moves."""
    for card, keep in TEAM_LIMIT.items():
        spots = [(p, i) for p, deck in enumerate(decks) for i, c in enumerate(deck) if c == card]
        if not spots:
            continue
        kind = next(k for k in ("attack", "power", "block", "skill") if any(str(c) == card for c in kinds[k]))
        others = [c for c in kinds[kind] if str(c) != card and str(c) not in TEAM_LIMIT]
        if not others:
            continue
        kept = int(dice.integers(len(spots))) if dice.random() < keep else None
        for n, (p, i) in enumerate(spots):
            if n != kept:
                decks[p][i] = str(dice.choice(others))
    return decks


def nobody_in_danger(rc):
    return all(real_danger(rc, s) == 0 for s in range(len(rc.allies)))


def gift_unusable(rc, R, name, t):
    """Coordinate (5 Strength this turn) or Believe in You (2 energy) given to player t, when t couldn't use it: they are knocked out
    or have ended their turn; for Coordinate, they have no attack they can play now; for Believe in You, the cards they'd want to play
    (an attack, a power, a skill that isn't Block, or Block while someone is in danger) don't cost more than the energy they have."""
    if not 0 <= t < len(rc.allies):
        return False
    ally = rc.allies[t]
    if not ally.is_alive() or ally.unit_id in rc.combat.ended_turn:
        return True
    if name == "Coordinate":
        return not any(R._static(ally.hand[h]).type == "attack" for h, _ in rc.legal_plays(t))
    danger = not nobody_in_danger(rc)
    wanted = 0
    for ref, cost in zip(ally.hand, rc.combat.hand_costs(ally)):
        s = R._static(ref)
        if cost is None or s.type in ("status", "curse") or (s.blocks and not danger):
            continue
        if cost < 0:                              # costs all your energy: more is always used
            return False
        wanted += cost
    return wanted <= ally.energy


def hits_intangible(rc, R, ref, t):
    """An attack on Intangible enemies only, so every hit does 1 damage, and it applies no Weak or Vulnerable to make up for it.
    t is an enemy's slot (4 and up) for a single-enemy attack, anything else for one that hits them all."""
    s = R._static(ref)
    if s.type != "attack" or {k for scope in s.statuses.values() for k in scope} & {"weak", "vulnerable"}:
        return False
    targets = [rc.enemies[t - 4]] if t >= 4 else list(rc.enemies)
    targets = [e for e in targets if e is not None and e.alive]
    return bool(targets) and all(R._statuses(e.unit).get("intangible", 0) > 0 for e in targets)


def hits_beaten(rc, R, ref, t):
    """An attack on enemies that can't be hurt any more: a Waterfall Giant brought down while holding Steam Eruption shows 0 HP,
    takes no harm and explodes on everyone two moves later (real_engine.EnemyView). Unless the attack applies Weak, which cuts the
    blast as it cuts any enemy attack. t as in hits_intangible."""
    s = R._static(ref)
    if s.type != "attack" or any("weak" in scope for scope in s.statuses.values()):
        return False
    targets = [rc.enemies[t - 4]] if t >= 4 else list(rc.enemies)
    targets = [e for e in targets if e is not None and e.alive]
    return bool(targets) and all(getattr(e.unit, "blowing", None) is not None for e in targets)


COVER_LEFT = 0.25                                 # cover: a teammate the coming hits would leave at or under this share of max HP


def low_in_danger(rc):
    """The agent's teammates whom the coming enemy turn would knock out or leave at or under COVER_LEFT of their max HP."""
    out = set()
    for s in range(1, len(rc.allies)):
        ally, danger = rc.allies[s], real_danger(rc, s)
        if ally.is_alive() and danger > 0 and ally.current_hp - danger <= COVER_LEFT * ally.max_hp:
            out.add(s)
    return out


def covers(rc, name, t, low):
    """Whether this card on seat t covers someone in `low`: Rally covers everyone, Lift its target, and Intercept its target only when
    the agent can take their hits on top of its own and still not end low itself."""
    if name == "Rally":
        return bool(low)
    if t not in low:
        return False
    if name == "Lift":
        return True
    if name == "Intercept":
        me = rc.allies[0]
        return me.current_hp - real_danger(rc, 0) - rc.incoming(t) > COVER_LEFT * me.max_hp
    return False


class Table:
    """One fight: shows it to the player, takes their moves and keeps the record."""
    YOU = 1

    def __init__(self, rc, R, dice):
        self.rc, self.R, self.dice = rc, R, dice
        self.names = {0: "Partner", 1: "You", 2: "Teammate"}
        self.t = Counter()
        self.events = []
        self.partner_waiting = False
        self.opening = False
        self.partner_played = False               # its last decision was a card
        self.shown_round = None
        self.ko_round = {}
        self._orig = {k: getattr(rc, k) for k in ("play", "bot_step", "_bot_answer", "_end_round", "_note", "end_turn")}
        rc.play, rc.bot_step, rc._bot_answer = self._play, self._step, self._answer
        rc._end_round, rc._note, rc.end_turn = self._end_round, self._note, self._end_turn

    # ------------------------------------------------------------ showing the table
    def enemy_label(self, t):
        return "abcdef"[t - 4]

    def target_label(self, t, card_target):
        if card_target == "single_enemy":
            return self.enemy_label(t)
        return {0: "p", 2: "t"}.get(t, "")

    def target_name(self, t, card_target):
        if card_target == "single_enemy":
            e = self.rc.enemies[t - 4]
            return e.unit.name if e is not None else "an enemy"
        if card_target == "single_ally":
            return "you" if t == self.YOU else self.names[t]
        return ""

    def intent_text(self, enemy):
        intent = self.rc.combat._enemy_dict(enemy).get("intent") or {}
        kind, name = intent.get("type"), intent.get("name", "")
        if kind == "attack":
            hit = intent.get("damage", {}).get(self.rc.allies[self.YOU].unit_id, intent.get("amount", 0))
            hits = intent.get("hits", 1) or 1
            more = " and gains Block" if intent.get("block") else ""
            return f"{name}: attacks every player for {hit} x {hits}{more}" if hits > 1 else f"{name}: attacks every player for {hit}{more}"
        if kind == "block":
            return f"{name}: gains Block"
        if kind == "stun":
            return "Stunned"
        return f"{name}: {str(kind).replace('_', ' ')}" if kind else "nothing"

    def status_parts(self, unit):
        return [f"{sid.replace('_', ' ').title()} {amount}" for sid, amount in self.R._statuses(unit).items() if amount]    # a spent Intercept stays at 0

    def status_text(self, unit):
        return ", ".join(self.status_parts(unit))

    def player_line(self, seat):
        rc = self.rc
        a = rc.allies[seat]
        name = self.names[seat]
        if not a.is_alive():
            return f"  {name:<9} knocked out"
        done = "  (ended turn)" if a.unit_id in rc.combat.ended_turn else ""
        statuses = self.status_text(a)
        statuses = "  " + statuses if statuses else ""
        return f"  {name:<9} {a.current_hp:>3}/{a.max_hp} HP  Block {a.block:<3} Energy {a.energy}/{a.max_energy}  would lose {real_danger(rc, seat):>3}{statuses}{done}"

    def hand_view(self, seat):
        """Each card in a player's hand as the page shows it."""
        rc = self.rc
        ally = rc.allies[seat]
        costs, blocks = rc.combat.hand_costs(ally), rc.combat.hand_blocks(ally)
        out = []
        for i, ref in enumerate(ally.hand):
            s = self.R._static(ref)
            try:
                text = self.card_text(self.R.create_card(ref), ally, blocks[i])
            except KeyError:
                text = ""
            out.append(dict(name=s.name, cost="-" if costs[i] is None else costs[i], text=text, type=s.type))
        return out

    def snapshot(self):
        """The whole table, for the page. It says nothing about which version the partner is, because the table doesn't know."""
        rc = self.rc
        enemies = [dict(letter=self.enemy_label(4 + e.slot), name=e.unit.name, hp=e.hp, max_hp=e.max_hp, block=e.block, alive=bool(e.alive),
                        statuses=self.status_parts(e.unit), next=self.intent_text(e.unit), attacks="attacks every player" in self.intent_text(e.unit),
                        intangible=self.R._statuses(e.unit).get("intangible", 0) > 0)
                   for e in rc.enemies if e is not None]
        players = []
        for seat in sorted(range(len(rc.allies)), key=lambda x: x != self.YOU):
            a = rc.allies[seat]
            alive = a.is_alive()
            players.append(dict(name=self.names[seat], you=seat == self.YOU, code={0: "p", 2: "t"}.get(seat, ""), hp=a.current_hp, max_hp=a.max_hp, block=a.block,
                                energy=a.energy, max_energy=a.max_energy, danger=real_danger(rc, seat), statuses=self.status_parts(a), alive=alive,
                                ended=a.unit_id in rc.combat.ended_turn, hand=self.hand_view(seat) if alive and seat != self.YOU else []))
        me = rc.allies[self.YOU]
        _, plays = self.legal_moves()
        hand = self.hand_view(self.YOU) if me.is_alive() else []
        for h, card in enumerate(hand):
            target = self.R._static(me.hand[h]).target
            card["moves"] = [dict(send=answer, to=self.target_label(t, target) or "you") for answer, t in plays.get(h, [])]
        return dict(round=rc.turn, enemies=enemies, players=players, hand=hand, can_wait=self._can_wait(), opening=self.opening, partner_waiting=self.partner_waiting)

    def legal_moves(self):
        """What the player can answer now, and for each card in hand its answers with their targets."""
        rc = self.rc
        me = rc.allies[self.YOU]
        targets = defaultdict(list)
        for h, t in rc.legal_plays(self.YOU):
            targets[h].append(t)
        options = ["e"] + (["w"] if self._can_wait() else [])
        plays = {}
        for h, ts in targets.items():
            target = self.R._static(me.hand[h]).target
            plays[h] = [(f"{h + 1}", ts[0])] if len(ts) == 1 else [(f"{h + 1}{self.target_label(t, target)}", t) for t in ts]
            options += [answer for answer, _ in plays[h]]
        return options, plays

    def show(self):
        rc = self.rc
        if UI is not None:
            if rc.turn != self.shown_round:
                self.shown_round = rc.turn
                print(f"Round {rc.turn}")
            UI.show_table(self.snapshot())
            return
        print(f"\n--- Round {rc.turn} ---")
        for e in rc.enemies:
            if e is None:
                continue
            statuses = self.status_text(e.unit)
            statuses = "  " + statuses if statuses else ""
            print(f"  [{self.enemy_label(4 + e.slot)}] {e.unit.name:<18} {e.hp:>4}/{e.max_hp} HP  Block {e.block}{statuses}")
            print(f"      next: {self.intent_text(e.unit)}")
        print()
        for seat in sorted(range(len(rc.allies)), key=lambda s: s != self.YOU):
            print(self.player_line(seat))
        for seat in range(len(rc.allies)):
            a = rc.allies[seat]
            if seat != self.YOU and a.is_alive():
                print(f"  {self.names[seat]}'s hand: " + (", ".join(self.R._static(r).name for r in a.hand) or "empty"))
        me = rc.allies[self.YOU]
        costs, blocks = rc.combat.hand_costs(me), rc.combat.hand_blocks(me)
        playable = {h for h, _ in rc.legal_plays(self.YOU)}
        print("\n  Your hand:")
        for i, ref in enumerate(me.hand):
            card = self.R.create_card(ref)
            try:
                text = self.card_text(card, me, blocks[i])
            except KeyError:
                text = ""
            cost = "-" if costs[i] is None else costs[i]
            print(f"   {'x' if i not in playable else ' '}{i + 1:>2}  {self.R._static(ref).name:<16} {cost!s:>2}E  {text}")
        if self.opening:
            print("\n  You can go first. Play what you like, then type w to let the others move.")
        elif self.partner_waiting:
            print("\n  Partner is waiting to see what you do.")

    @staticmethod
    def card_text(card, holder, block):
        from GameEngine.Cards._text import card_text
        return card_text(card, holder, block)

    # ------------------------------------------------------------ the player's moves
    def person_opens(self):
        """The person moves first in a round, for as long as they like. A wait (or their turn ending) hands over."""
        self.opening = True
        try:
            while self._step(self.YOU):
                pass
        finally:
            self.opening = False

    def _can_wait(self):
        rc = self.rc
        partner = rc.allies[0]
        return partner.is_alive() and partner.unit_id not in rc.combat.ended_turn

    def _step(self, seat):
        """As RealCombat.bot_step, with the player's moves in their seat. A wait is no action, so it returns False."""
        rc = self.rc
        if seat != self.YOU:
            return self._orig["bot_step"](seat)
        if seat >= len(rc.allies) or rc.result is not None or rc.combat.phase != self.R.CombatPhase.PLAYER_TURN:
            return False
        ally = rc.allies[seat]
        if not ally.is_alive():
            return False
        if rc.combat.choice_for(ally) is not None:
            rc._bot_answer(seat)
            return True
        if ally.unit_id in rc.combat.ended_turn:
            return False
        move = self.choose_move()
        if move[0] == "wait":
            print("  You wait.")
            return False
        if move[0] == "end":
            rc.end_turn(seat)
        else:
            rc.play(seat, move[1], move[2])
            while rc.result is None and rc.combat.choice_for(ally) is not None:
                rc._bot_answer(seat)
        return True

    def choose_move(self):
        rc = self.rc
        self.show()
        t0 = SAVE.seconds
        while True:
            legal = rc.legal_plays(self.YOU)
            me = rc.allies[self.YOU]
            targets = defaultdict(list)
            for h, t in legal:
                targets[h].append(t)
            options, _ = self.legal_moves()
            raw = ask("\nYour move (card number, w wait, e end, ? help): ", options).lower()
            match = re.fullmatch(r"(\d+)\s*([a-z]?)", raw)
            if raw in ("?", "help", "h"):
                print(HELP)
            elif raw in ("l", "look"):
                self.show()
            elif raw in ("q", "quit"):
                if yes("Stop for now? Your place is saved."):
                    raise QuitSession(undo=2)
            elif raw in ("e", "end"):
                if not legal or yes("You can still play a card. End your turn?"):
                    self._note_decision(t0)
                    return ("end",)
            elif raw in ("w", "wait"):
                if self._can_wait():
                    self.t["you_waits"] += 1
                    self._note_decision(t0)
                    return ("wait",)
                print("  Partner has finished, so there is nothing to wait for. Play a card or end your turn.")
            elif match:
                move = self._read_card(int(match.group(1)) - 1, match.group(2), targets, me)
                if move is not None:
                    self._note_decision(t0)
                    return move
            else:
                print("  Please type a card number, w, e or ?. Example: 2a plays your second card on enemy a.")

    def _read_card(self, h, letter, targets, me):
        if not 0 <= h < len(me.hand):
            print(f"  You have {len(me.hand)} cards.")
            return None
        if h not in targets:
            print(f"  You can't play {self.R._static(me.hand[h]).name} right now.")
            return None
        s = self.R._static(me.hand[h])
        ts = targets[h]
        if len(ts) == 1:
            return ("play", h, ts[0])
        labels = {self.target_label(t, s.target): t for t in ts}
        while letter not in labels:
            shown = ", ".join(f"{k} = {self.target_name(t, s.target)}" for k, t in labels.items())
            letter = ask(f"  {s.name} on whom? {shown}: ", list(labels)).lower()
            if letter in ("q", "quit"):
                return None
        return ("play", h, labels[letter])

    def _note_decision(self, t0):
        self.t["your_decisions"] += 1
        self.t["your_seconds"] += SAVE.seconds - t0

    def _answer(self, seat):
        """A question for the player; anyone else's goes to its bot as usual."""
        if seat != self.YOU:
            return self._orig["_bot_answer"](seat)
        rc = self.rc
        q = rc.pending_question(seat)
        announce("\n  Choose a card:")
        labels = {}
        for i, c in enumerate(q.options):
            try:
                text = self.card_text(self.R.create_card(c.ref), None, None)
            except KeyError:
                text = ""
            labels[str(i + 1)] = f"{c.defn.name}: {text}"
            if UI is None:
                print(f"    {i + 1}  {c.defn.name:<16} {text}")
        stop = q.min_picks == 0
        if stop:
            labels["0"] = "None of them"
            if UI is None:
                print("    0  none")
        options = [str(i + 1) for i in range(len(q.options))] + (["0"] if stop else [])
        while True:
            raw = ask("  Which one? ", options, labels)
            if raw in options:
                rc.answer_question([] if raw == "0" else [q.options[int(raw) - 1]], seat)
                return
            print("  Please type one of: " + ", ".join(options))

    # ------------------------------------------------------------ everyone's moves, told to the player, kept for the record
    def _fair_target(self, seat, h, t):
        """bots._pick takes the first legal target on a tie, which is the agent's seat. The scripted teammate breaks ties at
        random: a Block card among those who need it most, anything else among all of them."""
        rc = self.rc
        s = self.R._static(rc.allies[seat].hand[h])
        if s.target != "single_ally":
            return t
        options = [x for i, x in rc.legal_plays(seat) if i == h]
        if s.blocks:
            need = {x: real_danger(rc, x) for x in options}
            options = [x for x in options if need[x] == max(need.values())]
        return int(self.dice.choice(options)) if options else t

    def _play(self, seat, h, t):
        rc = self.rc
        if seat == 2:
            t = self._fair_target(seat, h, t)
        ally = rc.allies[seat]
        s = self.R._static(ally.hand[h])
        name = s.name.rstrip("+")
        if seat == 0 and name in ("Lift", "Intercept") and 1 <= t < len(rc.allies):
            self.t["partner_protect"] += 1
            self.t["partner_protect_covered"] += int(real_danger(rc, t) == 0)
            self.t["partner_protect_to_you"] += int(t == self.YOU)
        if seat == 0:
            self.t["partner_cards"] += 1
            if name == "Defend":
                self.t["partner_defend"] += 1
                self.t["partner_defend_no_need"] += int(real_danger(rc, 0) == 0)
            if name == "Rally":
                self.t["partner_rally"] += 1
                self.t["partner_rally_no_need"] += int(nobody_in_danger(rc))
            if s.type == "attack":
                self.t["partner_attacks"] += 1
                self.t["partner_attack_intangible"] += int(hits_intangible(rc, self.R, ally.hand[h], t))
                self.t["partner_attack_beaten"] += int(hits_beaten(rc, self.R, ally.hand[h], t))
            if name in ("Coordinate", "Believe in You"):
                self.t["partner_gift"] += 1
                self.t["partner_gift_unusable"] += int(gift_unusable(rc, self.R, name, t))
        target = self.target_name(t, s.target)
        enemies = {e.unit_id: e.current_hp + e.block for e in rc.combat.enemies}
        blocks, turn = [a.block for a in rc.allies], rc.turn
        out = self._orig["play"](seat, h, t)
        self.events.append((turn, seat, name, target))
        who = self.names[seat]
        verb = "play" if seat == self.YOU else "plays"
        told = f"  {who} {verb} {s.name}" + (f" on {target}" if target else "")
        parts = []
        if rc.turn == turn:
            dealt = sum(max(0, before - e.current_hp - e.block) for e in rc.combat.enemies for u, before in enemies.items() if u == e.unit_id)
            if dealt:
                parts.append(f"{dealt} damage")
            for i, (a, b) in enumerate(zip(rc.allies, blocks)):
                if a.block > b:
                    parts.append(f"{'you' if i == self.YOU else self.names[i]} +{a.block - b} Block")
        print(told + (": " + ", ".join(parts) if parts else "") + ".")
        return out

    def _note(self, results, before):
        rc = self.rc
        ids = {e.unit_id for e in rc.combat.enemies}
        for r in self.R._flat(results):
            seat = rc.seat_of.get(r.get("source_id"))
            if seat is not None and r.get("effect_id") == "instant_damage" and r.get("target_id") in ids:
                self.t[f"damage_{seat}"] += r.get("amount") or 0
                self.t[f"kills_{seat}"] += 1 if r.get("killed") else 0
        return self._orig["_note"](results, before)

    def _end_turn(self, seat):
        if seat != self.YOU:
            print(f"  {self.names[seat]} ends their turn.")
        return self._orig["end_turn"](seat)

    def _end_round(self):
        rc = self.rc
        hp = [a.current_hp for a in rc.allies]
        print("\n  The enemies act.")
        out = self._orig["_end_round"]()
        for seat, a in enumerate(rc.allies):
            name = self.names[seat]
            if hp[seat] > 0 and not a.is_alive():
                print(f"  {name} {'are' if seat == self.YOU else 'is'} knocked out.")
                self.ko_round.setdefault(seat, rc.turn)
            elif a.current_hp < hp[seat]:
                print(f"  {name} {'lose' if seat == self.YOU else 'loses'} {hp[seat] - a.current_hp} HP, now {a.current_hp}.")
            elif a.is_alive() and a.current_hp == hp[seat]:
                print(f"  {name} {'lose' if seat == self.YOU else 'loses'} nothing.")
        return out


def agent_move(env, obs, model, rules, table):
    """What the agent does: its own choice, minus what its rules take off the table for this decision, and then it picks again.
    timing: Lift and Intercept on a teammate, when no living teammate is in real danger.
    defend: Defend, when the agent itself is in no real danger (nothing coming, or its Block or someone's Intercept covers it).
    paced: one card at a time. After a card, its next decision is a Wait, when it may wait: the player gets a move, and w lets it go on.
    rally: Rally, when nobody would lose HP.
    gifts: Coordinate and Believe in You on someone who couldn't use them (gift_unusable).
    intangible: an attack whose every hit Intangible would cut to 1, unless it also applies Weak or Vulnerable (hits_intangible).
    beaten: an attack on enemies that can't be hurt any more (hits_beaten).
    cover: while a teammate would be knocked out or left low (low_in_danger) and the agent can play Lift or Intercept on them or Rally,
           only those may be played (covers). It doesn't stop a Wait or ending the turn."""
    from collab_agent.config import A_PLAY0, A_CHOOSE0, A_WAIT, N_TARGETS
    from collab_agent import real_engine as R
    c = env.combat
    mask = env.action_masks()
    me = c.players[0]
    if "paced" in rules and table.partner_played and env.dc is None and me.alive and mask[A_WAIT]:
        table.t["partner_paced_waits"] += 1
        return A_WAIT
    a = int(model.predict(obs, action_masks=mask, deterministic=True)[0])
    if not rules or env.dc is not None or not me.alive:
        return a

    def card(x):
        h, slot = divmod(x - A_PLAY0, N_TARGETS)
        return me.hand[h].defn.name.rstrip("+"), env.target_seat(slot)

    low = low_in_danger(c) if "cover" in rules else set()
    cover_now = bool(low) and any(mask[x] and covers(c, *card(x), low) for x in range(A_PLAY0, A_CHOOSE0))

    def barred(x):
        if not A_PLAY0 <= x < A_CHOOSE0:
            return False
        h, slot = divmod(x - A_PLAY0, N_TARGETS)
        name = me.hand[h].defn.name.rstrip("+")
        if cover_now:
            return not covers(c, name, env.target_seat(slot), low)
        if "beaten" in rules and hits_beaten(c, R, me.hand[h].ref, env.target_seat(slot)):
            return True
        if "timing" in rules and name in ("Lift", "Intercept") and 1 <= env.target_seat(slot) < len(c.allies):
            return all(real_danger(c, s) == 0 for s in range(1, len(c.allies)))
        if "rally" in rules and name == "Rally":
            return nobody_in_danger(c)
        if "gifts" in rules and name in ("Coordinate", "Believe in You"):
            return gift_unusable(c, R, name, env.target_seat(slot))
        if "intangible" in rules and hits_intangible(c, R, me.hand[h].ref, env.target_seat(slot)):
            return True
        return "defend" in rules and name == "Defend" and real_danger(c, 0) == 0

    if cover_now:
        table.t["partner_cover_needed"] += 1          # decisions, not turns
    if barred(a):
        table.t["partner_held_back"] += 1
        table.t["partner_cover_first"] += int(cover_now)
        mask = mask.copy()
        for x in range(A_PLAY0, A_CHOOSE0):
            if mask[x] and barred(x):
                mask[x] = False
        a = int(model.predict(obs, action_masks=mask, deterministic=True)[0])
    return a


def play_fight(session, env, plan, model, rules):
    from collab_agent.config import A_CHOOSE0, A_END, A_PLAY0, A_WAIT
    session.plan = plan
    obs, _ = env.reset()
    table = session.table
    done, info = False, {}
    while not done:
        a = agent_move(env, obs, model, rules, table)
        partner = env.combat.players[0]
        if env.dc is None and partner.alive:
            table.partner_played = A_PLAY0 <= a < A_CHOOSE0
            if a == A_WAIT:
                table.t["partner_waits"] += 1
                table.partner_waiting = True
            elif a == A_END:
                table.t["partner_turns"] += 1
        obs, _, done, _, info = env.step(a)
        table.partner_waiting = False
    return info["episode_summary"], table


def rate_fight(n, total):
    announce(f"\nThanks. A few quick questions about fight {n} of {total}. 1 = disagree, 5 = agree.")
    ratings = {}
    for key, text in QUESTIONS:
        while True:
            raw = ask(f"  {text} (1-5): ", ["1", "2", "3", "4", "5"], {"1": "Disagree", "5": "Agree"})
            if raw in ("1", "2", "3", "4", "5"):
                ratings[key] = int(raw)
                break
            print("    Please type a number from 1 to 5.")
    note = ask("  Anything you noticed about your partner? (press Enter to skip): ")
    return ratings, note


def record(table, env, summary, plan, version, block, n):
    rc = env.combat
    t = table.t
    damage = [t.get(f"damage_{i}", 0) for i in range(len(rc.allies))]
    kills = [t.get(f"kills_{i}", 0) for i in range(len(rc.allies))]
    alive = [bool(a.is_alive()) for a in rc.allies]
    rounds = int(summary["rounds"])
    sat_out = {str(i): rounds - table.ko_round.get(i, rounds) for i in range(1, len(alive)) if not alive[i]}
    profile = {k: float(v) for k, v in env.team_profiles.values.get(table.YOU, {}).items() if isinstance(v, (int, float))}
    return dict(kind="fight", n=n, block=block, version=version, lineup=list(plan["lineup"]), start_shares=plan["shares"], seed=plan["seed"],
                win=bool(summary["win"]), rounds=rounds, alive=alive, end_hp=[a.current_hp for a in rc.allies], max_hp=[a.max_hp for a in rc.allies],
                score=float(summary["score_std"]), damage=damage, kills=kills, sat_out=sat_out, counts=dict(t), your_profile=profile,
                events=[list(e) for e in table.events], deck=plan.get("deck"), decks=plan.get("decks"),
                **({"level": plan["level"]} if plan.get("level") else {}))


def make_plan(rng, R, cards=None, level=None):
    """One block's fight. level: one of LADDER, its pool's lineups; None (sessions before LAYOUT): an elite or a boss at even odds,
    drawn exactly as then, so an older session's seed still gives its fights."""
    pool = getattr(R, LADDER_POOLS[level]) if level else R.ELITES if rng.random() < .5 else R.BOSSES
    plan = dict(lineup=tuple(pool[int(rng.integers(len(pool)))]), shares=[float(rng.choice(LEVELS)) for _ in range(3)], seed=int(rng.integers(2 ** 31)))
    if level:
        plan["level"] = level
    return with_decks(plan, R, cards)


def lay_out(rng, R, cards, versions, blocks, layout):
    """The session's fights in order, as (block, plan, version). LAYOUT: block b climbs LADDER, and each block's order is a rotation of
    one random order, the rotations shuffled over the blocks, so with as many blocks as versions each version plays every place once.
    Earlier sessions: elites or bosses, each block's order drawn on its own, exactly as they were drawn then."""
    schedule = []
    if layout == LAYOUT:
        plans = [make_plan(rng, R, cards, LADDER[b % len(LADDER)]) for b in range(blocks)]
        first = list(versions)
        rng.shuffle(first)
        turns = [int(k) % len(first) for k in rng.permutation(blocks)]
        for b, plan in enumerate(plans):
            schedule += [(b, plan, str(v)) for v in first[turns[b]:] + first[:turns[b]]]
        return schedule
    for b, plan in enumerate([make_plan(rng, R, cards) for _ in range(blocks)]):
        order = list(versions)
        rng.shuffle(order)
        schedule += [(b, plan, str(v)) for v in order]
    return schedule


def with_decks(plan, R, cards, preset=None):
    """A deck preset at random (or the one given) and each player's deck, from dice of their own: the enemies, starting HP and seed
    are drawn exactly as before, so an older session's seed still gives its fights. No cards: every player keeps the trained deck."""
    if cards:
        import numpy as np
        dice = np.random.default_rng(plan["seed"] + 99991)
        names = list(DECK_PRESETS)
        plan["deck"] = preset or names[int(dice.integers(len(names)))]
        plan["decks"] = deal_decks(dice, R, cards, plan["deck"], 3)
    return plan


def load_saved(path):
    """The answers to play back, and how many fights are already written."""
    answers, fights = [], 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["kind"] == "answer":
                answers.append(r)
            elif r["kind"] == "undo":
                del answers[len(answers) - r["answers"]:]
            elif r["kind"] == "fight":
                fights += 1
    return answers, fights


def unfinished(out, name):
    """This player's latest session that can carry on: (its file, its first row), or None."""
    clean = re.sub(r"[^A-Za-z0-9_-]+", "_", name)[:40] or "player"
    for path in sorted(glob.glob(os.path.join(out, f"{clean}_*.jsonl")), reverse=True):
        with open(path, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f]
        head = rows[0]
        fights, picks = sum(r["kind"] == "fight" for r in rows), sum(r["kind"] == "favourite" for r in rows)
        left = fights < len(head["versions"]) * head["fights_each"] or (head.get("layout") == LAYOUT and picks < head["fights_each"])
        if head.get("saved_answers") and head["name"] == name and left:
            return path, head
    return None


def run_session(args, resume=None):
    global SAVE
    announce("Loading the game and your partner...")
    import numpy as np
    import torch
    torch.set_num_threads(2)
    from sb3_contrib import MaskablePPO
    import evaluate as EV
    import collab_agent.env as E
    from collab_agent import real_engine as R
    from collab_agent.bots import Bot
    from GameEngine.Combat.combat import CombatPhase
    R.CombatPhase = CombatPhase

    class HumanBot(Bot):
        name = "human"

        def act(self, combat, seat):
            raise RuntimeError("the player's moves go through Table._step")

    stamp = time.strftime("%Y%m%d_%H%M%S")
    seed = args.seed if args.seed is not None else int(time.time())
    rng = np.random.default_rng(seed)
    versions = args.versions.split(",")
    for v in versions:
        if v not in VERSIONS:
            raise SystemExit(f"unknown version {v}; choose from {', '.join(VERSIONS)}")
    models = {path: MaskablePPO.load(path, device="cpu") for path in {VERSIONS[v][0] for v in versions}}

    make_bot = E.make_bot
    E.make_bot = lambda kind, r: HumanBot() if kind == "human" else make_bot(kind, r)
    session = type("Session", (), {})()
    dice = np.random.default_rng(seed + 1)
    orig_new_fight = R.new_fight

    def new_fight(_rng, seats, cfg):
        plan = session.plan
        for seat, deck in zip(seats, plan.get("decks") or ()):
            seat.deck = list(deck)
        rc = R.start_fight(plan["lineup"], seats, cfg.real_ally, plan["seed"])
        rc.set_start_hp(plan["shares"][:len(rc.allies)])
        session.table = Table(rc, R, dice)
        return rc

    def lead():
        """The start of a round: the person first, then the scripted teammate's usual chance of acting before the agent looks."""
        session.table.person_opens()
        c = env.combat
        for p in c.players[1:]:
            if p is not None and p.seat != Table.YOU and p.alive and env.rng.random() < env.cfg.teammate_lead_prob:
                for _ in range(int(env.rng.integers(1, 3))):
                    c.bot_step(p.seat)

    R.new_fight = new_fight
    base = VERSIONS[versions[0]][0]
    cfg = dataclasses.replace(EV.load_config(base), team_fights=10 ** 6, start_hp=None, min_teammates=1, max_teammates=3)
    kinds = ["human"] + (["continuous"] if args.players == 3 else [])
    env = E.CollabEnv(cfg, seed=seed, fixed_team=kinds)
    env.set_ctime(cfg.final.total_timesteps)
    env._teammate_lead = lead

    name = re.sub(r"[^A-Za-z0-9_-]+", "_", args.name)[:40] or "player"
    os.makedirs(args.out, exist_ok=True)
    path = resume or os.path.join(args.out, f"{name}_{stamp}.jsonl")
    todo, written = load_saved(resume) if resume else ([], 0)
    layout, picked = LAYOUT, set()                # picked: blocks whose favourite is already in the file
    if resume:
        with open(resume, encoding="utf-8") as f:
            saved = [json.loads(line) for line in f]
        layout = saved[0].get("layout")
        picked = {r.get("block") for r in saved if r["kind"] == "favourite"}
    presets = getattr(args, "deck_presets", True)
    cards = cfg.real_deck if presets else None
    schedule = lay_out(rng, R, cards, versions, args.fights_each, layout)

    if UI is not None:
        UI.clear_notice()
    if not resume:
        how = "Type p to pause, or q to stop for now and carry on later." if UI is None else "You can pause or stop for now at any time with the buttons at the top, and carry on later."
        levels = []                                   # each block's level, in order (a block's fights come together)
        for b, plan, _ in schedule:
            if b == len(levels):
                levels.append(plan["level"])
        named = ", then ".join(("an " if lv[0] in "aeiou" else "a ") + lv + " fight" for lv in levels)
        announce(f"""
Welcome, and thanks for testing. You'll play {len(schedule)} co-op fights next to an AI partner, roughly 5 to 20 minutes each.
They come in sets: {named}. Each set is one fight played {len(versions)} times, with the partner playing differently each time,
and after each set you'll pick the partner you liked most in it. Please play the way you normally would.
After each fight you'll answer a few quick questions. There are no right answers.
Your answers are saved to this computer only, as you give them. {how}""")
        if UI is None:
            print(HELP)

    done = 0
    with open(path, "a", encoding="utf-8") as f:
        def write(row):
            f.write(json.dumps(row) + "\n")
            f.flush()

        welcome = f"\nWelcome back. You've finished {written} of {len(schedule)} fights. Here's where you stopped" + (" (? for help).\n" if UI is None else ".")
        SAVE = Saved(write, todo, args.name, welcome)
        if resume:
            write(dict(kind="resumed", time=stamp))
        else:
            write(dict(kind="session", name=args.name, time=stamp, seed=seed, players=args.players, versions=versions, fights_each=args.fights_each,
                       table=TABLE, no_practice=bool(args.no_practice), saved_answers=True, screen="page" if UI is not None else "terminal",
                       rules={v: list(VERSIONS[v][1]) for v in versions}, deck_presets=bool(presets), layout=LAYOUT))
        SAVE.hide_screen()
        try:
            if not args.no_practice and yes("Play a practice fight first? It doesn't count"):
                print("\n=== Practice fight. Type q at any time to finish it early. ===" if UI is None else "=== Practice fight ===")
                if UI is not None:
                    UI.set_heading("Practice fight")
                model = models[VERSIONS[versions[0]][0]]
                try:
                    plan = with_decks(dict(lineup=("byrdonis",), shares=[1.0, 1.0, 1.0], seed=int(rng.integers(2 ** 31))), R, cards, "Default")
                    summary, _ = play_fight(session, env, plan, model, VERSIONS[versions[0]][1])
                    announce("\nYou won the practice fight." if summary["win"] else "\nYou lost the practice fight.")
                except QuitSession:
                    announce("\nPractice over.")
            for n, (b, plan, version) in enumerate(schedule, start=1):
                deck = (f" · {plan['level'].capitalize()} fight" if plan.get("level") else "") + (f" · {plan['deck']} deck" if plan.get("deck") else "")
                print(f"\n=== Fight {n} of {len(schedule)}{deck} ===")
                if UI is not None:
                    UI.set_heading(f"Fight {n} of {len(schedule)}{deck}")
                path_v, rules = VERSIONS[version]
                t0 = SAVE.seconds
                summary, table = play_fight(session, env, plan, models[path_v], rules)
                if UI is not None:
                    UI.show_table(table.snapshot())
                announce("\nThe team won!" if summary["win"] else "\nThe team lost.")
                row = record(table, env, summary, plan, version, b, n)
                row["seconds"] = SAVE.seconds - t0
                row["ratings"], row["note"] = rate_fight(n, len(schedule))
                if n > written:                       # played back from an earlier sitting: already in the file
                    write(row)
                done += 1
                if layout == LAYOUT and (n == len(schedule) or schedule[n][0] != b):      # the block's last fight: its favourite
                    nums = [i for i, (bb, _, _) in enumerate(schedule, start=1) if bb == b]
                    best = ask(f"Of the {plan['level']} fight, fights {nums[0]} to {nums[-1]}, which partner did you like most? "
                               f"({', '.join(map(str, nums))}, or Enter to skip): ", [str(i) for i in nums], {str(i): f"Fight {i}" for i in nums})
                    if b not in picked:
                        write(dict(kind="favourite", block=b, level=plan["level"], fight=int(best) if best.isdigit() else None))
            if layout != LAYOUT:
                announce("\nFights finished. One last question.")
                best = ask(f"Which fight's partner did you like most? (1-{len(schedule)}, or Enter to skip): ", [str(i + 1) for i in range(len(schedule))],
                           {str(i + 1): f"Fight {i + 1}" for i in range(len(schedule))})
                write(dict(kind="favourite", fight=int(best) if best.isdigit() else None))
        except QuitSession as stop:
            SAVE.show_screen(say_where=False)
            if stop.undo:
                write(dict(kind="undo", answers=stop.undo))
            announce(f"\nStopping here. Your place is saved. To carry on later:\n  {carry_on_line()}")
        write(dict(kind="end", fights_finished=done))
    SAVE.show_screen(say_where=False)
    SAVE = Saved()
    E.make_bot, R.new_fight = make_bot, orig_new_fight
    announce(f"\nThanks for playing. {done} fights saved to {path}")
    return path


def report(out):
    rows = []
    files = sorted(glob.glob(os.path.join(out, "*.jsonl")))
    players = {}
    favourites = Counter()
    by_level = defaultdict(Counter)               # favourites picked per fight level (LAYOUT sessions)
    older = []
    for path in files:
        fights = {}
        who = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r["kind"] == "session":
                    who = r["name"]
                    if r.get("table") != TABLE or not r.get("saved_answers"):      # an earlier table, or typed before the page existed: not comparable
                        older.append(os.path.basename(path))
                        break
                elif r["kind"] == "fight":
                    r["player"] = who
                    rows.append(r)
                    fights[r["n"]] = r
                    players[who] = r.get("your_profile", {})
                elif r["kind"] == "favourite" and r.get("fight") in fights:
                    favourites[fights[r["fight"]]["version"]] += 1
                    if r.get("level"):
                        by_level[r["level"]][fights[r["fight"]]["version"]] += 1
    print(f"{len(rows)} rated fights from {len(players)} players in {len(files) - len(older)} sessions, in {out}")
    if older:
        print(f"Left out, played on an earlier setup: {', '.join(older)}")
    if not rows:
        return
    print("With this few players, read these as a direction only. Margins are 95% over fights and don't cover differences between people.")

    def mean_margin(xs):
        n = len(xs)
        m = sum(xs) / n
        if n < 3:                                 # one or two fights can't give a margin
            return m, None
        return m, 1.96 * (sum((x - m) ** 2 for x in xs) / (n - 1)) ** .5 / n ** .5

    plus_minus = lambda e: " " * 7 if e is None else f" +-{e:4.1f}"

    versions = sorted({r["version"] for r in rows})
    print("\nRatings, 1 = disagree, 5 = agree")
    print(f"{'':58s}" + "".join(f"{v:>16s}" for v in versions))
    for key, text in QUESTIONS:
        row = f"{text:58s}"
        for v in versions:
            m, e = mean_margin([r["ratings"][key] for r in rows if r["version"] == v])
            row += f"{m:9.2f}{plus_minus(e)}"
        print(row)

    print("\nThe same fights, each version minus 'best', per block (ratings)")
    for v in versions:
        if v == "best":
            continue
        for key, text in QUESTIONS:
            diffs = []
            for a in rows:
                if a["version"] == v:
                    for b in rows:
                        if b["version"] == "best" and b["player"] == a["player"] and b["block"] == a["block"] and b["seed"] == a["seed"]:
                            diffs.append(a["ratings"][key] - b["ratings"][key])
            if diffs:
                m, e = mean_margin(diffs)
                print(f"  {v:14s} {text:58s} {m:+5.2f}{plus_minus(e)} (n {len(diffs)})")

    print("\nWhat happened")
    head = ("fights", "win %", "you alive %", "you: damage %", "partner: damage %", "partner: Waits/turn", "protect on covered %", "protect to you %",
            "Defend, no need %", "Rally, no need %", "gifts unusable %", "hits Intangible /fight", "partner before you %", "partner in a row %", "you: s per move")

    def partner_before_you(sel):
        """Of the partner's cards in rounds you both played, the share that came before your first card."""
        before = total = 0
        for r in sel:
            rounds = defaultdict(list)
            for turn, seat, *_ in r["events"]:
                rounds[turn].append(seat)
            for seats in rounds.values():
                if 0 in seats and 1 in seats:
                    before += seats[:seats.index(1)].count(0)
                    total += seats.count(0)
        return 100 * before / max(total, 1)

    def partner_in_a_row(sel):
        """Of the partner's cards, the share played straight after its own last card, with no card from anyone between."""
        run = total = 0
        for r in sel:
            last = None
            for turn, seat, *_ in r["events"]:
                if seat == 0:
                    total += 1
                    run += int(last == (turn, 0))
                last = (turn, seat)
        return 100 * run / max(total, 1)

    print(f"{'':16s}" + "".join(f"{h:>22s}" for h in head))
    for v in versions:
        sel = [r for r in rows if r["version"] == v]
        n = len(sel)
        share = lambda i: 100 * sum(r["damage"][i] for r in sel) / max(sum(sum(r["damage"]) for r in sel), 1)
        c = Counter()
        for r in sel:
            c.update(r["counts"])
        vals = (n, 100 * sum(r["win"] for r in sel) / n, 100 * sum(r["alive"][1] for r in sel) / n, share(1), share(0),
                c["partner_waits"] / max(c["partner_turns"], 1), 100 * c["partner_protect_covered"] / max(c["partner_protect"], 1),
                100 * c["partner_protect_to_you"] / max(c["partner_protect"], 1), 100 * c["partner_defend_no_need"] / max(c["partner_defend"], 1),
                100 * c["partner_rally_no_need"] / max(c["partner_rally"], 1), 100 * c["partner_gift_unusable"] / max(c["partner_gift"], 1),
                c["partner_attack_intangible"] / n,
                partner_before_you(sel), partner_in_a_row(sel), c["your_seconds"] / max(c["your_decisions"], 1))
        print(f"{v:16s}" + "".join(f"{x:22.1f}" for x in vals))
    if favourites:
        print("\nFavourite partner: " + ", ".join(f"{v} {n}" for v, n in favourites.most_common())
              + ("  (one pick per session before the ladder layout, one per fight level since)" if by_level else ""))
        for lv in LADDER:
            if by_level.get(lv):
                print(f"  {lv:<6} " + ", ".join(f"{v} {n}" for v, n in by_level[lv].most_common()))
    levels = [lv for lv in LADDER if any(r.get("level") == lv for r in rows)]
    if levels:
        print("\nBy fight level (ladder sessions)")
        print(f"{'':16s}{'fights':>8s}{'win %':>8s}{'rounds':>8s}{'again':>8s}{'you alive %':>13s}")
        for lv in levels:
            sel = [r for r in rows if r.get("level") == lv]
            print(f"{lv:16s}{len(sel):8d}{100 * sum(r['win'] for r in sel) / len(sel):8.1f}{sum(r['rounds'] for r in sel) / len(sel):8.1f}"
                  f"{sum(r['ratings']['again'] for r in sel) / len(sel):8.2f}{100 * sum(r['alive'][1] for r in sel) / len(sel):13.1f}")

    decks = sorted({r.get("deck") or "trained deck" for r in rows})
    if len(decks) > 1 or decks != ["trained deck"]:
        print("\nBy deck")
        print(f"{'':16s}{'fights':>8s}{'win %':>8s}{'rounds':>8s}{'again':>8s}{'you: HP lost %':>16s}")
        for d in decks:
            sel = [r for r in rows if (r.get("deck") or "trained deck") == d]
            lost = sum(1 - r["end_hp"][1] / (r["max_hp"][1] * r["start_shares"][1]) for r in sel) / len(sel)
            print(f"{d:16s}{len(sel):8d}{100 * sum(r['win'] for r in sel) / len(sel):8.1f}{sum(r['rounds'] for r in sel) / len(sel):8.1f}"
                  f"{sum(r['ratings']['again'] for r in sel) / len(sel):8.2f}{100 * lost:16.1f}")

    print("\nEach player's profile at their last fight (the same three numbers the scripted bots have)")
    for who, p in players.items():
        print(f"  {who:20s} " + " ".join(f"{k} {p[k]:+.2f}" for k in ("A", "S", "T") if k in p))

    print("\nNotes")
    for r in rows:
        if r.get("note"):
            print(f"  {r['player']} fight {r['n']} ({r['version']}): {r['note']}")


def main():
    os.chdir(HERE)
    sys.path.insert(0, HERE)
    sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description="A person plays next to the agent without knowing which version it is, and rates each fight.")
    ap.add_argument("--name", help="the player's name or a nickname; saved with their answers on this computer")
    ap.add_argument("--versions", default="best,best_paced,best_paced_rules", help=f"comma-separated, from {', '.join(VERSIONS)}")
    ap.add_argument("--fights-each", type=int, default=3, help="fights per version, one per block: every version plays the same fights, "
                                                                 "the blocks climbing easy, elite, boss")
    ap.add_argument("--players", type=int, choices=(2, 3), default=3, help="3: the player, the agent and a scripted teammate; 2: the player and the agent")
    ap.add_argument("--seed", type=int, default=None, help="for repeating a session's fights and order")
    ap.add_argument("--no-practice", action="store_true", help="skip the offer of a practice fight")
    ap.add_argument("--out", default=OUT_DIR, help="where the results go")
    ap.add_argument("--resume", action="store_true", help="carry on from the last session this --name didn't finish")
    ap.add_argument("--carry-on", action="store_true", help="as --resume when this --name has an unfinished session, otherwise start a new one")
    ap.add_argument("--fixed-deck", action="store_true", help="every player keeps the trained deck instead of a random deck preset each fight")
    ap.add_argument("--terminal", action="store_true", help="play by typing here, without the browser page")
    ap.add_argument("--no-browser", action="store_true", help="don't open the page, only print its address")
    ap.add_argument("--report", action="store_true", help="summarise every session in --out and stop")
    args = ap.parse_args()
    if args.report:
        report(args.out)
    elif not args.name:
        ap.error("give --name (a nickname is fine), or --report")
    else:
        path = None
        if args.resume or args.carry_on:
            found = unfinished(args.out, args.name)
            if found is None and args.resume:
                print(f"{args.name} has no unfinished session to carry on. To start a new one, leave out --resume.")
                return
            if found is not None:
                path, head = found
                args.seed, args.versions, args.fights_each, args.players, args.no_practice = head["seed"], ",".join(head["versions"]), head["fights_each"], head["players"], head["no_practice"]
                args.fixed_deck = not head.get("deck_presets", False)       # a session from before the presets keeps the trained deck
        args.deck_presets = not args.fixed_deck
        if not args.terminal:
            global UI
            from playtest_ui import PlayUI
            again = (f"Double-click play.bat again and type the same name, {args.name}." if os.environ.get("PLAYTEST_LAUNCHER") == "play.bat"
                     else f'cd "{HERE}"; python playtest.py --name {args.name} --resume')
            UI = PlayUI(again, open_browser=not args.no_browser)
            UI.start()
        try:
            run_session(args, resume=path)
        finally:
            if UI is not None:
                UI.finish()
                UI = None


if __name__ == "__main__":
    main()
