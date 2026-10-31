from ._enemy import Enemy
from ...Effects.InstantEffects.instant_damage import InstantDamage
from ...Effects.InstantEffects.instant_block import InstantBlock
from ...Effects.InstantEffects.instant_add_card import InstantAddCard


class Move:
    """One thing an enemy can do on its turn.

    `effects(enemy, context)` builds what it does; `kind`, `damage` and `hits`
    are what the client is shown as the intent. `damage` is per hit, before
    the enemy's own Strength.

    Every move lands on every living player. The game has no single-target
    enemy move: MonsterModel.PerformMove hands each move all the players
    (combatState.PlayerCreatures), and an attack built with FromMonster
    targets all opponents. Intercept is how one player takes the others' hits.
    """

    ATTACK = "attack"
    BLOCK = "block"
    BUFF = "buff"
    DEBUFF = "debuff"
    SUMMON = "summon"
    SLEEP = "sleep"

    def __init__(self, name, kind, effects, damage=0, hits=1, block=0):
        self.name = name
        self.kind = kind
        self.effects = effects
        self.damage = damage
        self.hits = hits
        # Block this move gives the enemy, as printed. The intent shows it
        # scaled for the party, which is what the enemy will actually gain.
        self.block = block


# The moves most Act 1 enemies are made of. Anything else is written out.

def players(context):
    """Who an enemy's move lands on: every player still standing."""
    return [ally for ally in context.all_allies if ally.is_alive()]


def attack(name, damage, hits=1, block=0, inflict=None, gain=None):
    """An Attack: `hits` hits of `damage` on every player, then any riders -
    `inflict=(Frail, 2)` on every player (Flyconid's Frail Spores),
    `gain=(Strength, 2)` for the attacker (Cubex's Repeater Blast), `block` for
    the attacker (Nibbit's Hesitant Slice). Hit by hit, each hit landing on
    everyone before the next, as the game's AttackCommand does. The intent
    still reads as an attack."""
    def effects(enemy, context):
        out = []
        targets = players(context)
        for hit in range(hits):
            for p in targets:
                # Which hit of the attack it is, for whoever counts hits rather
                # than targets (Fossil Stalker's Suck).
                damage_effect = InstantDamage(source=enemy, target=p, amount=damage)
                damage_effect.hit = hit
                out.append(damage_effect)
        if inflict is not None:
            status, amount = inflict
            out.extend(status(source=enemy, target=p, amount=amount) for p in targets)
        if gain is not None:
            status, amount = gain
            out.append(status(source=enemy, target=enemy, amount=amount))
        if block:
            out.append(InstantBlock(source=enemy, target=enemy, amount=block))
        return out
    return Move(name, Move.ATTACK, effects, damage=damage, hits=hits, block=block)


def buff(name, status, amount):
    """Gain `amount` of a status: Hiss, Clap, Inhale are all Strength."""
    return Move(name, Move.BUFF,
                lambda enemy, context: [status(source=enemy, target=enemy, amount=amount)])


def debuff(name, status, amount):
    """Put `amount` of a status on every player: Roar, Track, Shrinker,
    Constrict."""
    def effects(enemy, context):
        return [status(source=enemy, target=p, amount=amount) for p in players(context)]
    return Move(name, Move.DEBUFF, effects)


def guard(name, block):
    """Gain Block and nothing else (Crossbow Raider's Reload)."""
    return Move(name, Move.BLOCK,
                lambda enemy, context: [InstantBlock(source=enemy, target=enemy, amount=block)],
                block=block)


def hand_out(card_id, amount=1, pile=InstantAddCard.DISCARD):
    """Effects putting `amount` of a status card into every player's pile -
    the discard, as the game does for Slimed and Infection."""
    def effects(enemy, context):
        return [InstantAddCard(source=enemy, target=p, card_id=card_id, pile=pile,
                               amount=amount)
                for p in players(context)]
    return effects


class Branch:
    """One option in a random choice of move - the game's RandomBranchState.

    `repeat` is how often in a row it may come up: FOREVER, NO_REPEAT (never
    twice in a row), ONCE (once per fight), or a number N (at most N in a
    row). `cooldown` c rules it out while it is among the last c moves.
    `weight` is its share among the options still allowed."""

    FOREVER = "forever"
    NO_REPEAT = 1
    ONCE = "once"

    def __init__(self, move, repeat=FOREVER, cooldown=0, weight=1.0):
        self.move = move
        self.repeat = repeat
        self.cooldown = cooldown
        self.weight = weight

    def weight_after(self, history):
        """This option's weight given the moves so far (oldest first)."""
        if self.repeat == Branch.ONCE:
            if any(move is self.move for move in history):
                return 0.0
        elif self.repeat != Branch.FOREVER:
            n = self.repeat
            if len(history) >= n and all(move is self.move for move in history[-n:]):
                return 0.0
        if self.cooldown and any(move is self.move for move in history[-self.cooldown:]):
            return 0.0
        return self.weight


class ScriptedEnemy(Enemy):
    """An enemy that follows a move list: `pick_move(turn)` says which, and
    may pick at random among Branches (`choose`)."""

    # Base HP is the single-player number; Combat scales it for co-op, and
    # sets block_scale, which the resolver applies to Block this enemy gains.
    CATEGORY = "normal"
    # The wiki gives most enemies a range, "HP 32-35", rolled once per fight.
    # Set this and DEFAULT_MAX_HP / DEFAULT_HP_VARIANCE are not consulted.
    HP_RANGE = None
    # What the client shows. The class name stands in when this is not set.
    NAME = None

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        ranged = max_hp is None and self.HP_RANGE is not None
        if ranged:
            # No rng: the top of the range, the game's HP before its roll
            # (Creature starts at MaxInitialHp) - never an unseeded draw. The
            # fight rolls it as the enemy enters (Combat._roll_hp).
            max_hp = rng.randint(*self.HP_RANGE) if rng is not None else self.HP_RANGE[1]
            hp_variance = 0
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        if ranged:
            self.hp_range = tuple(self.HP_RANGE)
            self.hp_unrolled = rng is None
        if self.NAME is not None:
            self.name = self.NAME
        self.turn = 0
        self.move = None
        self.block_scale = 1.0
        # The rng it chooses moves with: which move a slime picks must not
        # depend on how many players shuffled their decks first. The session
        # and summons set the fight's MonsterAi stream here; None falls back
        # to that stream too.
        self.rng = rng
        # Every move chosen, oldest first - what the repeat rules read.
        self.history = []
        # The context of the intent being chosen, for a pick_move that needs
        # the rng (Fogmog) or the fight's counters (a Two-Tailed Rat's budget).
        self.context = None
        # Summoning. `leader` is who called this enemy in; Combat marks a
        # death resolved once on_death has run and any minions have left.
        self.leader = None
        self.death_resolved = False
        # Set by on_death to come back: enemy phases to sit out, then revive.
        self.revive_in = 0
        # Set by Combat when a stun skipped the move: it is made next turn
        # instead, as the game's stunned move hands back to it.
        self.skipped_move = False

    def pick_move(self, turn):
        raise NotImplementedError

    def choose(self, branches):
        """A random move among `branches`, under their repeat rules."""
        weights = [branch.weight_after(self.history) for branch in branches]
        total = sum(weights)
        if total <= 0:
            # Every option ruled out (Flyconid after Vulnerable, Frail, Smash).
            # The game's loop then falls through to its first branch, since
            # 0 - 0 <= 0 passes on the first test; so does this.
            return branches[0].move
        roll = self._move_rng().random() * total
        for branch, weight in zip(branches, weights):
            roll -= weight
            if weight > 0 and roll <= 0:
                return branch.move
        return next(b.move for b, w in zip(branches, weights) if w > 0)

    def choose_index(self, n):
        """A random number below `n`, from the same stream as `choose` - for a
        start an encounter picks at random (Corpse Slugs)."""
        return self._move_rng().randrange(n)

    def _move_rng(self):
        if self.rng is not None:
            return self.rng
        # The fight's MonsterAi stream, as the game rolls moves.
        rngs = getattr(self.context, "rngs", None)
        return rngs.monster_ai if rngs is not None else self.context.rng

    def same_kind_index(self, context):
        """Where this enemy stands among the living enemies of its own kind -
        the game's encounter slots (Wriggler 1-4, a front and a back Nibbit)."""
        mine = [e for e in (context.all_enemies if context is not None else [])
                if type(e) is type(self)]
        return mine.index(self) if self in mine else 0

    def on_combat_start(self, context):
        """Effects as the fight begins (the game's AfterAddedToRoom): Cubex's
        opening Block and Artifact, Aeonglass's Withering Presence."""
        return []

    # Debuffs that last only the turn (Dark Shackles): an Illusion keeps them
    # through its death and they run out as usual. The game's ITemporaryPower.
    TEMPORARY_DEBUFFS = ("strength_loss_this_turn",)

    def on_death(self, context):
        """Effects to resolve as this enemy dies, before the fight can end -
        Phrog Parasite's Wrigglers. Default: an Illusion schedules a revival,
        if the leader who cast it is still standing. As the game's
        IllusionPower, it shows a Revive intent until then, and loses its
        debuffs (not the ones that last the turn); its buffs stay."""
        if self.get_status("illusion") is not None and (
                self.leader is None or self.leader.is_alive()):
            self.revive_in = 1
            self.statuses = {sid: status for sid, status in self.statuses.items()
                             if not status.IS_DEBUFF or sid in self.TEMPORARY_DEBUFFS}
            self.intent = {"type": "heal", "name": "Revive", "amount": 0, "hits": 1, "block": 0}
        return []

    def escape(self):
        """Leave the fight (Fat Gremlin's Flee): out of it like the dead, but
        not killed - no death of its own runs, and nothing reacts to one."""
        self.escaped = True
        self.current_hp = 0
        self.death_resolved = True
        self.intent = None

    def revive(self):
        """Back at full HP. Statuses are kept; Combat chooses the next intent
        along with everyone else's."""
        self.current_hp = self.max_hp
        self.block = 0
        self.death_resolved = False
        self.intent = None

    def choose_intent(self, context=None):
        self.context = context
        if self.skipped_move and self.move is not None:
            # Stunned through it: the same move again, the pattern held.
            self.skipped_move = False
        else:
            self.move = self.pick_move(self.turn)
            self.turn += 1
            self.history.append(self.move)
        self.intent = {
            "type": self.move.kind,
            "name": self.move.name,
            "amount": self.move.damage,
            "hits": self.move.hits,
            # Scaled, so it matches what the resolver will actually grant:
            # Reload's 3 reads 6 with two players, not 3.
            "block": scaled_block(self.move.block, self.block_scale),
        }

    def get_effects(self, context):
        return self.move.effects(self, context)


# Real STS2 co-op scaling: enemy HP is multiplied by the player count and an
# act factor. Single player is unscaled.
ACT_SCALING = {"act1": 1.1, "act2": 1.2, "act3": 1.2, "act3boss": 1.3}


def hp_scale(player_count, act="act1"):
    if player_count <= 1:
        return 1.0
    return player_count * ACT_SCALING.get(act, 1.0)


def scaled_block(amount, scale):
    """Block an enemy gains from `amount`, after co-op scaling and before its
    own statuses. The one rule both the resolver and the intents use, so what
    the players are shown is what the enemy gets. Rounded, as the reference
    does: Reload's 3 at three players is 3 x 3.3 = 9.9, which blocks 10."""
    if scale == 1.0:
        return amount
    return round(amount * scale)


def block_scale(player_count, act="act1"):
    # Block scales harder than HP for two players: flat x2, no act factor.
    if player_count <= 1:
        return 1.0
    if player_count == 2:
        return 2.0
    return player_count * ACT_SCALING.get(act, 1.0)
