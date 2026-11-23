"""Scripted teammates with known playstyles (from MockUpRB/History, plus Support).

Each bot takes ONE action per call, so the agent's Wait can let them act first.
"""


def _need(combat, seat):
    p = combat.players[seat]
    return max(0, combat.incoming(seat) - p.block)


def _weakest_enemy_target(combat):
    alive = combat.living_enemies()
    return 4 + min(alive, key=lambda e: e.hp + e.block).slot if alive else None


def _kills_itself(combat, seat, card):
    """A card whose HP cost would knock its player out (Bloodletting, Offering, Hemokinesis, Blood Wall, Brand, Breakthrough at
    low HP): its effects' HP lost (real_engine.card_effects) is at least the player's HP. The mock's cards have no effects."""
    fx = getattr(card, "effects", None)
    return bool(fx) and fx[0] >= combat.players[seat].hp


def _pick(combat, seat, score, dice=None):
    """Choose the legal play with the highest score; None scores are skipped. End turn if nothing.
    When several targets of the chosen card share that score, `dice` picks one of them. Without dice it is
    the first, and for a teammate's Lift, Intercept, Coordinate or Believe in You the first is always seat 0,
    the agent: scripted teammates then send it about 90% of those cards.
    A card whose HP cost would knock the bot out is never chosen (_kills_itself). Only the random bot and the
    mistakes of the blend bot can still play one."""
    p = combat.players[seat]
    best, best_s, same = None, None, []
    for h, t in combat.legal_plays(seat):
        if _kills_itself(combat, seat, p.hand[h]):
            continue
        s = score(combat, seat, p.hand[h], t)
        if s is None:
            continue
        if best_s is None or s > best_s:
            best, best_s, same = (h, t), s, [t]
        elif s == best_s and h == best[0]:
            same.append(t)
    if best is None:
        return ("end",)
    return ("play", best[0], best[1] if dice is None or len(same) == 1 else int(dice.choice(same)))


def _attack_score(combat, seat, card, t):
    d = card.defn
    if d.damage <= 0:
        return None
    if d.target == "single_enemy" and t != _weakest_enemy_target(combat):
        return None
    dmg = combat.shown_damage(combat.players[seat], card)
    return dmg / max(1, d.cost) + (3 if d.name == "Bash" else 0)


def _block_score(combat, seat, card, t):
    d = card.defn
    if d.block <= 0:
        return None
    if d.target == "single_ally":
        return 1 + _need(combat, t) / 10
    if d.target == "all_ally":
        return 1 + sum(_need(combat, q.seat) for q in combat.living_players()) / 15
    return 1 + _need(combat, seat) / 10


def _other_score(combat, seat, card, t):
    d = card.defn
    if d.damage > 0 or d.block > 0:
        return None
    if d.target == "single_enemy" and t != _weakest_enemy_target(combat):
        return None
    return 0.5


class Bot:
    name = "bot"
    ties = None      # dice for _pick's ties between targets, handed out by make_bot. None: the first target

    def set_ties(self, dice):
        """This bot's dice for ties; a bot that plays through other bots (continuous, change) shares them."""
        self.ties = dice
        for part in vars(self).values():
            if isinstance(part, Bot):
                part.ties = dice

    def act(self, combat, seat):
        raise NotImplementedError

    def answer(self, combat, seat, q):
        # exhaust the cards this style values least, at least min_picks
        ranked = sorted(q.options, key=lambda c: self.card_value(c))
        n = max(q.min_picks, min(q.max_picks, sum(1 for c in ranked if self.card_value(c) < 1)))
        return ranked[:n]

    def card_value(self, card):
        return 1.0

    def on_turn_end(self):
        pass


class AggressiveBot(Bot):
    """Bash > Strike > Defend (MockUpRB play_aggressive)."""
    name = "aggressive"

    def act(self, combat, seat):
        def score(c, s, card, t):
            a = _attack_score(c, s, card, t)
            if a is not None:
                return 10 + a
            o = _other_score(c, s, card, t)
            if o is not None:
                return 5 + o
            return _block_score(c, s, card, t)
        return _pick(combat, seat, score, self.ties)

    def card_value(self, card):
        return 0.0 if card.defn.block > 0 else 2.0


class DefensiveBot(Bot):
    """Defend > Strike > Bash (MockUpRB play_defensive)."""
    name = "defensive"

    def act(self, combat, seat):
        def score(c, s, card, t):
            b = _block_score(c, s, card, t)
            if b is not None:
                return 10 + b
            a = _attack_score(c, s, card, t)
            if a is not None:
                return 5 - card.defn.cost      # cheap attacks before Bash
            return _other_score(c, s, card, t)
        return _pick(combat, seat, score, self.ties)

    def card_value(self, card):
        return 0.0 if card.defn.damage > 0 else 2.0


class CheeseBot(Bot):
    """Blocks only while the incoming hit isn't covered, then attacks (MockUpRB play_cheese)."""
    name = "cheese"

    def act(self, combat, seat):
        def score(c, s, card, t):
            d = card.defn
            if d.block > 0:
                needer = t if d.target == "single_ally" else s
                if d.target == "all_ally":
                    if sum(_need(c, q.seat) for q in c.living_players()) <= 0:
                        return None
                elif _need(c, needer) <= 0:
                    return None
                return 20 + _block_score(c, s, card, t)
            a = _attack_score(c, s, card, t)
            if a is not None:
                return 10 + a
            return _other_score(c, s, card, t)
        return _pick(combat, seat, score, self.ties)


class RandomBot(Bot):
    name = "random"

    def __init__(self, rng):
        self.rng = rng

    def act(self, combat, seat):
        plays = combat.legal_plays(seat)
        if not plays or self.rng.random() < 0.1:
            return ("end",)
        h, t = plays[int(self.rng.integers(len(plays)))]
        return ("play", h, t)

    def answer(self, combat, seat, q):
        n = int(self.rng.integers(q.min_picks, q.max_picks + 1))
        idx = self.rng.choice(len(q.options), size=n, replace=False)
        return [q.options[i] for i in idx]


class ChangeOfHeartBot(Bot):
    """Aggressive for a while, then switches to defensive for good (MockUpRB AChangeOfHeart)."""
    name = "change"

    def __init__(self, rng):
        self.switch_turn = int(rng.integers(4, 16))
        self.turns = 0
        self.aggr, self.defn = AggressiveBot(), DefensiveBot()

    @property
    def style(self):
        return self.aggr if self.turns < self.switch_turn else self.defn

    def act(self, combat, seat):
        return self.style.act(combat, seat)

    def answer(self, combat, seat, q):
        return self.style.answer(combat, seat, q)

    def on_turn_end(self):
        self.turns += 1


class SupportBot(Bot):
    """Team cards first: covers whoever is about to be hit, Vulnerable/Weak, Rally Cry, then attacks."""
    name = "support"

    def act(self, combat, seat):
        def score(c, s, card, t):
            d = card.defn
            if "team" in d.groups:
                if d.block > 0:
                    b = _block_score(c, s, card, t)
                    return 20 + b if b > 1 else None   # only block someone who needs it
                o = _other_score(c, s, card, t)
                a = _attack_score(c, s, card, t)
                if o is None and a is None:
                    return None
                return 15 + (a or 0)
            a = _attack_score(c, s, card, t)
            if a is not None:
                return 10 + a
            b = _block_score(c, s, card, t)
            if b is not None:
                return 5 + b
            return _other_score(c, s, card, t)
        return _pick(combat, seat, score, self.ties)


def _build_score(combat, seat, card, t):
    d = card.defn
    if "scale" not in d.groups or (d.target == "single_enemy" and t != _weakest_enemy_target(combat)):
        return None
    return 1.0


def _team_score(combat, seat, card, t):
    d = card.defn
    if "team" not in d.groups or (d.target == "single_enemy" and t != _weakest_enemy_target(combat)):
        return None
    return _block_score(combat, seat, card, t) if d.block > 0 else 1.0


class BlendBot(Bot):
    """One player's own mix instead of a set style, rolled per bot, so teams cover the range
    between the named styles and the side none of them play (building up first). Each action it
    draws what it feels like doing by its leanings and plays the best card of that kind, else of
    the next kind drawn; `mistake` of the time it plays anything, or ends the turn early."""
    name = "blend"
    KINDS = (_attack_score, _block_score, _build_score, _team_score)

    def __init__(self, rng):
        self.dice = rng                       # not `rng`: real_engine answers questions at random for a bot that has one
        self.leanings = rng.dirichlet([1.0] * len(self.KINDS))     # attack, block, build up, team
        self.mistake = float(rng.uniform(0, 0.25))

    def act(self, combat, seat):
        if self.dice.random() < self.mistake:
            plays = combat.legal_plays(seat)
            if not plays or self.dice.random() < 0.2:
                return ("end",)
            h, t = plays[int(self.dice.integers(len(plays)))]
            return ("play", h, t)
        for k in self.dice.choice(len(self.KINDS), size=len(self.KINDS), replace=False, p=self.leanings):
            action = _pick(combat, seat, self.KINDS[k], self.ties)
            if action[0] == "play":
                return action
        return _pick(combat, seat, _other_score, self.ties)


class ContinuousBot(Bot):
    """Between aggressive and defensive: each action it plays as AggressiveBot with probability
    x, else as DefensiveBot. x is rolled per bot, uniform from 0 to 1."""
    name = "continuous"

    def __init__(self, rng):
        self.dice = rng                       # not `rng`: real_engine answers questions at random for a bot that has one
        self.x = float(rng.uniform(0, 1))
        self.aggr, self.defn = AggressiveBot(), DefensiveBot()

    def _style(self):
        return self.aggr if self.dice.random() < self.x else self.defn

    def act(self, combat, seat):
        return self._style().act(combat, seat)

    def answer(self, combat, seat, q):
        return self._style().answer(combat, seat, q)


def _tag_score(tag):
    """Scores the cards the analyzer tags `tag` (Block as _block_score, damage as _attack_score)."""
    def score(combat, seat, card, t):
        d = card.defn
        if tag not in d.groups or (d.target == "single_enemy" and t != _weakest_enemy_target(combat)):
            return None
        if d.block > 0:
            return _block_score(combat, seat, card, t)
        return _attack_score(combat, seat, card, t) if d.damage > 0 else 1.0
    return score


def _prefer(combat, seat, score, dice=None):
    """The best card `score` likes; with none in hand, the best of anything else, so a turn is not wasted."""
    for fallback in (score, _attack_score, _block_score, _other_score):
        action = _pick(combat, seat, fallback, dice)
        if action[0] == "play":
            return action
    return ("end",)


class TagBot(Bot):
    """Plays the cards with one analyzer tag first, then anything else."""
    tag = None

    def act(self, combat, seat):
        return _prefer(combat, seat, _tag_score(self.tag), self.ties)


class NowBot(TagBot):
    name = tag = "now"


class SelfBot(TagBot):
    name = tag = "self"


class TeamBot(TagBot):
    name = tag = "team"


class ScaleBot(Bot):
    """Builds up first: scale cards first for the first `build_turns` turns of each fight (rolled
    per bot, 2 to 4), then it plays for now, like NowBot."""
    name = "scale"

    def __init__(self, rng):
        self.build_turns = int(rng.integers(2, 5))

    def act(self, combat, seat):
        return _prefer(combat, seat, _tag_score("scale" if combat.turn <= self.build_turns else "now"), self.ties)


# What --teammates may name. EnvConfig.teammate_types is the default mix: the named styles only.
BOT_KINDS = ("aggressive", "defensive", "cheese", "random", "change", "support", "blend", "continuous",
             "scale", "now", "self", "team")


def make_bot(kind, rng):
    """A teammate bot. With an rng it also gets dice of its own for ties between targets (see _pick), from a
    stream beside the rng's: the rng's own numbers come out as before, so a fight's other draws do not move.
    Without one (a bot made directly, like the Cheese stand-in in the agent's seat) ties go to the first target."""
    bot = _make_bot(kind, rng)
    if rng is not None:
        bot.set_ties(rng.spawn(1)[0])
    return bot


def _make_bot(kind, rng):
    return {
        "aggressive": lambda: AggressiveBot(),
        "defensive": lambda: DefensiveBot(),
        "cheese": lambda: CheeseBot(),
        "random": lambda: RandomBot(rng),
        "change": lambda: ChangeOfHeartBot(rng),
        "support": lambda: SupportBot(),
        "blend": lambda: BlendBot(rng),
        "continuous": lambda: ContinuousBot(rng),
        "scale": lambda: ScaleBot(rng),
        "now": lambda: NowBot(),
        "self": lambda: SelfBot(),
        "team": lambda: TeamBot(),
    }[kind]()
