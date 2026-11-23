"""Mock Slay the Spire 2-style co-op combat engine.

This stands in for your real Game Engine. The environment only uses the public
methods of `Combat` (see README, "Plugging in the real engine").

Targets use one index everywhere:  t = 0-3 -> player seat t,  t = 4-9 -> enemy slot t-4.
Cards that don't pick a target use t = 0.
"""
import math
from .cards import Card, make_deck
from .config import N_PLAYERS, N_ENEMIES, HAND_SIZE

DURATION_STATUSES = ("vulnerable", "weak", "frail")


class Unit:
    def __init__(self, max_hp):
        self.max_hp = max_hp
        self.hp = max_hp
        self.block = 0
        self.statuses = {}

    @property
    def alive(self):
        return self.hp > 0

    def st(self, name):
        return self.statuses.get(name, 0)

    def add_status(self, name, amount):
        v = self.statuses.get(name, 0) + amount
        if v == 0:
            self.statuses.pop(name, None)
        else:
            self.statuses[name] = v


class Player(Unit):
    def __init__(self, seat, max_hp, deck, bot=None, max_energy=3):
        super().__init__(max_hp)
        self.seat = seat
        self.deck = deck            # master deck (kept between fights)
        self.bot = bot              # None for the agent
        self.max_energy = max_energy
        self.energy = 0
        self.draw, self.hand, self.discard, self.exhaust = [], [], [], []
        self.ended = False
        self.history = None         # this turn's record for the Characteristic Analyzer
        self.agent_block = 0        # how much of this player's Block the agent gave (teammates only)

    def reset_for_fight(self, rng):
        self.hp, self.block, self.statuses = self.max_hp, 0, {}
        self.agent_block = 0
        self.draw = list(self.deck)
        rng.shuffle(self.draw)
        self.hand, self.discard, self.exhaust = [], [], []
        self.ended = False
        self.history = None


class Intent:
    def __init__(self, kinds=(), damage=0, hits=0, target=None, block=0, buff=None, debuff=None):
        self.kinds = set(kinds)     # subset of {attack, block, buff, debuff, other}
        self.damage, self.hits, self.target = damage, hits, target
        self.block = block
        self.buff = buff or {}
        self.debuff = debuff or {}


class Enemy(Unit):
    def __init__(self, slot, max_hp, attack):
        super().__init__(max_hp)
        self.slot = slot
        self.attack = attack
        self.intent = Intent()
        self.owners = {}            # status -> {seat: stacks}, who applied each debuff


class Question:
    """A card asking its player to choose cards (answered by the env's Divide and Conquer for the agent)."""

    def __init__(self, seat, card, options, min_picks, max_picks, draw_per_pick):
        self.seat, self.card = seat, card
        self.options = options
        self.min_picks, self.max_picks = min_picks, max_picks
        self.draw_per_pick = draw_per_pick


def new_stats():
    return {
        "damage": [0.0] * N_PLAYERS,         # HP damage dealt to enemies, capped at HP before the hit
        "kills": [0] * N_PLAYERS,
        "useful_block": [0.0] * N_PLAYERS,   # by giver, already divided by the receiver's max HP
        "hp_lost_frac": [0.0] * N_PLAYERS,   # by receiver, HP lost / max HP
        "knockouts": 0,
        "rounds": 0,
        # for the collaborative scoring (all about the AGENT, seat 0)
        "vuln_applied": 0,                   # times the agent applied an increase-damage-taken debuff
        "weak_applied": 0,                   # times the agent applied a reduce-damage debuff
        "block_to_ally": [0.0] * N_PLAYERS,  # raw Block the agent gave each teammate seat
        "bonus_damage": 0.0,                 # extra HP damage teammates dealt thanks to the agent's debuffs
        "hp_saved": 0.0,                     # HP teammates kept thanks to the agent's Weak and Block
        "vuln_cashed": 0.0,                  # teammates' hits on an enemy with the agent's Vulnerable (x its share)
        "weak_cashed": 0.0,                  # enemy hits on a teammate where the agent's Weak saved HP (x its share)
        "block_cashed": 0.0,                 # enemy hits on a teammate that the agent's Block soaked up
        "complement": 0.0,                   # f_0_variant3's term, worked out by the env at round end
    }

INCREASE_DAMAGE_TAKEN = {"vulnerable"}
REDUCE_DAMAGE = {"weak"}


def agent_share(enemy, status):
    """Fraction of an enemy's stacks of `status` that the agent applied."""
    if enemy.st(status) <= 0:
        return 0.0
    owners = enemy.owners.get(status, {})
    total = sum(owners.values())
    return owners.get(0, 0) / total if total > 0 else 0.0


class Combat:
    def __init__(self, rng, players, enemies):
        self.rng = rng
        self.players = players + [None] * (N_PLAYERS - len(players))
        self.enemies = enemies + [None] * (N_ENEMIES - len(enemies))
        self.turn = 1
        self.result = None          # None, "win", "lose"
        self.question = None        # open Question, if any
        self.stats = new_stats()
        self.finished_histories = {}  # seat -> last completed turn history (read by the analyzer)
        self.total_enemy_max_hp = sum(e.max_hp for e in enemies)
        self.version = 0            # bumps on every change (for waited_since_last_change)

    # ------------------------------------------------------------ helpers
    def living_players(self):
        return [p for p in self.players if p is not None and p.alive]

    def living_enemies(self):
        return [e for e in self.enemies if e is not None and e.alive]

    def ally_hp_scale(self):
        return max(p.max_hp for p in self.players if p is not None)

    def enemy_hp_scale(self):
        return max(e.max_hp for e in self.enemies if e is not None)

    def enemy_hit(self, enemy, player, ignore_weak=False):
        """Damage per hit of enemy's intent on player, after modifiers."""
        dmg = enemy.intent.damage + enemy.st("strength")
        if enemy.st("weak") > 0 and not ignore_weak:
            dmg *= 0.75
        if player.st("vulnerable") > 0:
            dmg *= 1.5
        return max(0, math.floor(dmg))

    def incoming(self, seat):
        p = self.players[seat]
        total = 0
        for e in self.living_enemies():
            if "attack" in e.intent.kinds and e.intent.target == seat:
                total += self.enemy_hit(e, p) * e.intent.hits
        return total

    def card_hit(self, player, card, enemy=None):
        d = card.defn
        if d.damage <= 0:
            return 0
        dmg = d.damage + player.st("strength")
        if player.st("weak") > 0:
            dmg *= 0.75
        if enemy is not None and enemy.st("vulnerable") > 0:
            dmg *= 1.5
        return max(0, math.floor(dmg))

    def card_block(self, player, card):
        d = card.defn
        if d.block <= 0:
            return 0
        blk = d.block + player.st("dexterity")
        if player.st("frail") > 0:
            blk *= 0.75
        return max(0, math.floor(blk))

    # ------------------------------------------------------------ setup
    @classmethod
    def new_fight(cls, rng, players, hp_per_player=65, atk_per_player=8):
        n = len(players)
        n_enemies = int(rng.integers(1, 4))
        budget = hp_per_player * n
        shares = rng.dirichlet([2.0] * n_enemies)
        enemies = []
        for i in range(n_enemies):
            hp = max(15, int(budget * shares[i]))
            atk = max(4, int(round(atk_per_player * n / n_enemies * rng.uniform(0.8, 1.2))))
            enemies.append(Enemy(i, hp, atk))
        for p in players:
            p.reset_for_fight(rng)
        c = cls(rng, players, enemies)
        for e in enemies:
            c.roll_intent(e)
        c.start_turn()
        return c

    def roll_intent(self, e):
        alive = [p.seat for p in self.living_players()]
        target = int(self.rng.choice(alive))
        r = self.rng.random()
        if r < 0.55:
            e.intent = Intent({"attack"}, e.attack, 1, target)
        elif r < 0.70:
            hits = int(self.rng.integers(2, 4))
            e.intent = Intent({"attack"}, max(1, round(e.attack / hits * 1.1)), hits, target)
        elif r < 0.80:
            e.intent = Intent({"block"}, block=e.attack)
        elif r < 0.90:
            e.intent = Intent({"buff"}, buff={"strength": 2})
        else:
            debuff = {"weak": 2} if self.rng.random() < 0.5 else {"vulnerable": 2}
            e.intent = Intent({"attack", "debuff"}, max(1, e.attack // 2), 1, target, debuff=debuff)

    # ------------------------------------------------------------ turn flow
    def start_turn(self):
        for p in self.living_players():
            if p.st("barricade") <= 0:
                p.block = 0
                p.agent_block = 0
            p.energy = p.max_energy
            p.ended = False
            self.draw_cards(p, 5)
            p.history = {"E_total": p.max_energy, "used": [], "leftover": [],
                         "intent": self.incoming(p.seat), "start_block": p.block}
        self.version += 1

    def draw_cards(self, p, n):
        for _ in range(n):
            if not p.draw:
                if not p.discard:
                    return
                p.draw = p.discard
                p.discard = []
                self.rng.shuffle(p.draw)
            card = p.draw.pop()
            if len(p.hand) >= HAND_SIZE:
                p.discard.append(card)      # full hand -> discard (engine fix from the input spec)
            else:
                p.hand.append(card)

    def can_play(self, seat, card):
        p = self.players[seat]
        d = card.defn
        if "unplayable" in d.keywords or d.cost > p.energy:
            return False
        return bool(self.valid_targets(seat, card))

    def valid_targets(self, seat, card):
        t = card.defn.target
        if t in ("single_enemy",):
            return [4 + e.slot for e in self.living_enemies()]
        if t == "single_ally":
            return [q.seat for q in self.living_players() if q.seat != seat]
        if t in ("all_enemy", "random_enemy") and not self.living_enemies():
            return []
        return [0]

    def legal_plays(self, seat):
        p = self.players[seat]
        out = []
        for h, card in enumerate(p.hand):
            if self.can_play(seat, card):
                out.extend((h, t) for t in self.valid_targets(seat, card))
        return out

    def play(self, seat, h, t):
        """Play hand slot h on target t. Returns a Question if the card asks one."""
        p = self.players[seat]
        card = p.hand.pop(h)
        d = card.defn
        # what the card showed in hand, before it is played: the analyzer compares
        # it with the shown values of the cards left over (end_turn)
        shown = [d.cost, self.shown_damage(p, card), self.card_block(p, card), set(d.groups)]
        p.energy -= d.cost
        self.version += 1

        # --- damage
        if d.damage > 0:
            if d.target == "single_enemy":
                targets = [self.enemies[t - 4]]
            elif d.target == "random_enemy":
                targets = [self.rng.choice(self.living_enemies())]
            elif d.target == "all_enemy":
                targets = self.living_enemies()
            else:
                targets = []
            for e in targets:
                for _ in range(d.hits):
                    if e.alive:
                        share = agent_share(e, "vulnerable") if seat != 0 else 0.0
                        without = min(e.hp, max(0, self.card_hit(p, card) - e.block)) if share else 0
                        hp_dmg = self.damage_enemy(seat, e, self.card_hit(p, card, e))
                        if share:
                            self.stats["bonus_damage"] += (hp_dmg - without) * share
                            self.stats["vuln_cashed"] += share

        # --- block
        if d.block > 0:
            amount = self.card_block(p, card)
            if d.target == "single_ally":
                receivers = [self.players[t]]
            elif d.target == "all_ally":
                receivers = self.living_players()
            else:
                receivers = [p]
            for r in receivers:
                self.give_block(seat, r, amount)

        # --- statuses
        for recipient, sts in d.statuses.items():
            if recipient == "self":
                units = [p]
            elif recipient == "target":
                units = [self.enemies[t - 4]] if t >= 4 else [self.players[t]]
            elif recipient == "all_allies":
                units = self.living_players()
            else:
                units = self.living_enemies()
            for u in units:
                if u.alive:
                    for name, amt in sts.items():
                        self.apply_status(seat, u, name, amt)

        p.history["used"].append(shown)
        self.check_end()

        # --- question
        if d.choice and self.result is None:
            kind, mn, mx, draw_per = d.choice
            options = list(p.hand)
            if options and mx > 0:
                self.question = Question(seat, card, options, min(mn, len(options)),
                                         min(mx, len(options)), draw_per)
                return self.question
        self.move_played(p, card)
        return None

    def answer_question(self, picks):
        """Finish the open question with the chosen cards (a list of Card objects)."""
        q = self.question
        p = self.players[q.seat]
        for c in picks:
            if c in p.hand:
                p.hand.remove(c)
                p.exhaust.append(c)
        self.draw_cards(p, q.draw_per_pick * len(picks))
        self.move_played(p, q.card)
        self.question = None
        self.version += 1

    def move_played(self, p, card):
        d = card.defn
        if d.type == "power":
            return                                  # powers leave play
        if "exhaust" in d.keywords:
            p.exhaust.append(card)
        else:
            p.discard.append(card)

    def apply_status(self, seat, u, name, amt):
        u.add_status(name, amt)
        if isinstance(u, Enemy) and amt > 0:
            owners = u.owners.setdefault(name, {})
            owners[seat] = owners.get(seat, 0) + amt
            if seat == 0:
                if name in INCREASE_DAMAGE_TAKEN:
                    self.stats["vuln_applied"] += 1
                if name in REDUCE_DAMAGE:
                    self.stats["weak_applied"] += 1

    def damage_enemy(self, seat, e, amount):
        absorbed = min(e.block, amount)
        e.block -= absorbed
        hp_dmg = min(e.hp, amount - absorbed)
        e.hp -= hp_dmg
        self.stats["damage"][seat] += hp_dmg
        if e.hp <= 0:
            e.hp = 0
            e.statuses = {}
            e.owners = {}
            self.stats["kills"][seat] += 1
        return hp_dmg

    def give_block(self, giver, receiver, amount):
        need = max(0, self.incoming(receiver.seat) - receiver.block)
        useful = min(amount, need)
        receiver.block += amount
        self.stats["useful_block"][giver] += useful / receiver.max_hp
        if giver == 0 and receiver.seat != 0:
            self.stats["block_to_ally"][receiver.seat] += amount
            receiver.agent_block += amount
        return amount

    def end_turn(self, seat):
        p = self.players[seat]
        p.ended = True
        p.history["leftover"] = [[c.defn.cost, self.shown_damage(p, c), self.card_block(p, c), set(c.defn.groups)]
                                 for c in p.hand if c.defn.cost > 0]
        # as the player saw it when they ended: the hit aimed at them now, and their Block
        # (their own, plus what teammates gave them this turn)
        p.history["intent"] = self.incoming(seat)
        p.history["end_block"] = p.block
        self.version += 1
        if all(q.ended for q in self.living_players()):
            self.resolve_round()

    def shown_damage(self, p, card):
        d = card.defn
        per_hit = self.card_hit(p, card)
        n_targets = len(self.living_enemies()) if d.target == "all_enemy" else 1
        return per_hit * d.hits * n_targets

    def check_end(self):
        if self.result is None:
            if not self.living_enemies():
                self.result = "win"
            elif not self.living_players():
                self.result = "lose"

    def resolve_round(self):
        # 1. player end of turn
        for p in self.living_players():
            keep = [c for c in p.hand if "retain" in c.defn.keywords]
            for c in p.hand:
                if c in keep:
                    continue
                (p.exhaust if "ethereal" in c.defn.keywords else p.discard).append(c)
            p.hand = keep
        # 2. hand the turn's history to the Characteristic Analyzer (before it's cleared)
        self.finished_histories = {p.seat: p.history for p in self.players if p is not None and p.history}
        for p in self.players:
            if p is not None:
                p.history = None    # handed over once: a knocked-out player gets no new one to repeat
        # 3. enemy turn
        for e in self.living_enemies():
            e.block = 0
        for e in self.living_enemies():
            it = e.intent
            if "attack" in it.kinds:
                target = self.players[it.target]
                if not target.alive:
                    alive = self.living_players()
                    if not alive:
                        break
                    target = alive[int(self.rng.integers(len(alive)))]
                share = agent_share(e, "weak") if target.seat != 0 else 0.0
                for _ in range(it.hits):
                    hit = self.enemy_hit(e, target)
                    if share and target.alive:
                        lost = min(target.hp, max(0, hit - target.block))
                        lost_without = min(target.hp, max(0, self.enemy_hit(e, target, ignore_weak=True) - target.block))
                        self.stats["hp_saved"] += (lost_without - lost) * share
                        if lost_without > lost:
                            self.stats["weak_cashed"] += share
                    self.damage_player(target, hit)
                if it.debuff and target.alive:
                    for name, amt in it.debuff.items():
                        target.add_status(name, amt)
            if "block" in it.kinds:
                e.block += it.block
            for name, amt in it.buff.items():
                e.add_status(name, amt)
        self.check_end()
        if self.result is not None:
            return
        # 4. end of round
        for u in self.living_players() + self.living_enemies():
            for name in DURATION_STATUSES:
                if u.st(name) > 0:
                    u.add_status(name, -1)
                    if u.st(name) <= 0 and isinstance(u, Enemy):
                        u.owners.pop(name, None)
        for e in self.living_enemies():
            self.roll_intent(e)
        self.turn += 1
        self.stats["rounds"] += 1
        # 5. turn start
        self.start_turn()

    def damage_player(self, p, amount):
        if not p.alive:
            return
        absorbed = min(p.block, amount)
        p.block -= absorbed
        hp_dmg = min(p.hp, amount - absorbed)
        # The agent's Block on a teammate is taken last: whatever this hit took of it
        # would otherwise have come off their HP.
        soaked = max(0, p.agent_block - p.block)
        if soaked:
            p.agent_block -= soaked
            saved = min(p.hp, amount - absorbed + soaked) - hp_dmg
            if saved > 0:
                self.stats["hp_saved"] += saved
                self.stats["block_cashed"] += 1
        p.hp -= hp_dmg
        self.stats["hp_lost_frac"][p.seat] += hp_dmg / p.max_hp
        if p.hp <= 0:
            p.hp = 0
            p.ended = True
            self.stats["knockouts"] += 1

    # ------------------------------------------------------------ scripted teammates
    def bot_step(self, seat):
        """Let the bot at `seat` take one action (a play, with its answer, or end turn)."""
        p = self.players[seat]
        if p is None or not p.alive or p.ended or self.result is not None:
            return False
        action = p.bot.act(self, seat)
        if action[0] == "end":
            self.end_turn(seat)
        else:
            q = self.play(seat, action[1], action[2])
            if q is not None:
                self.answer_question(p.bot.answer(self, seat, q))
        return True

    def bot_finish_turn(self, seat):
        turn = self.turn
        while self.turn == turn and self.bot_step(seat):
            pass

    def pending_question(self, seat):
        """A question waiting on `seat` that no play of theirs returned. Here questions only
        come from the agent's own plays (play() returns them), so never; the real engine
        (real_engine.py) can ask at other times."""
        return None


def make_players(rng, bots, agent_hp=None):
    """Seat 0 = agent (bot None), then one seat per teammate bot."""
    players = [Player(0, agent_hp or int(rng.integers(60, 91)), make_deck(rng))]
    for i, bot in enumerate(bots, start=1):
        players.append(Player(i, int(rng.integers(60, 91)), make_deck(rng), bot=bot))
    return players


# the two entry points env.py uses, the same in real_engine.py
def make_team(rng, bots, cfg):
    return make_players(rng, bots)


def new_fight(rng, players, cfg):
    return Combat.new_fight(rng, players, cfg.enemy_hp_per_player, cfg.enemy_atk_per_player)
