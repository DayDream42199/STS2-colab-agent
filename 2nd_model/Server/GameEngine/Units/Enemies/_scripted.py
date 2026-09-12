import random

from ._enemy import Enemy
from ...Effects.InstantEffects.instant_damage import InstantDamage
from ...Effects.InstantEffects.instant_block import InstantBlock
from ...Effects.InstantEffects.instant_add_card import InstantAddCard


class Move:
    """One thing an enemy can do on its turn.

    `effects(enemy, context)` builds what it does; `kind`, `damage` and `hits`
    are what the client is shown as the intent. `damage` is per hit, before
    the enemy's own Strength.
    """

    ATTACK = "attack"
    BLOCK = "block"
    BUFF = "buff"
    DEBUFF = "debuff"

    def __init__(self, name, kind, effects, damage=0, hits=1, targeted=None):
        self.name = name
        self.kind = kind
        self.effects = effects
        self.damage = damage
        self.hits = hits
        # Whether one player is picked for it. Attacks always; a debuff aimed
        # at one player (Aeonglass's Intensity) opts in.
        self.targeted = (kind == Move.ATTACK) if targeted is None else targeted


# The moves most Act 1 enemies are made of. Anything else is written out.

def attack(name, damage, hits=1, block=0, inflict=None, gain=None):
    """An Attack: `hits` hits of `damage` at the announced target, then any
    riders, in the reference's order - `inflict=(Frail, 2)` on the target
    (Flyconid's Frail Spores), `gain=(Strength, 2)` for the attacker (Cubex's
    Repeater Blast), `block` for the attacker (Nibbit's Hesitant Slice). The
    intent still reads as an attack, as the reference shows it."""
    def effects(enemy, context):
        out = []
        if context.target is not None:
            out.extend(InstantDamage(source=enemy, target=context.target, amount=damage)
                       for _ in range(hits))
            if inflict is not None:
                status, amount = inflict
                out.append(status(source=enemy, target=context.target, amount=amount))
        if gain is not None:
            status, amount = gain
            out.append(status(source=enemy, target=enemy, amount=amount))
        if block:
            out.append(InstantBlock(source=enemy, target=enemy, amount=block))
        return out
    return Move(name, Move.ATTACK, effects, damage=damage, hits=hits)


def buff(name, status, amount):
    """Gain `amount` of a status: Hiss, Clap, Inhale are all Strength."""
    return Move(name, Move.BUFF,
                lambda enemy, context: [status(source=enemy, target=enemy, amount=amount)])


def debuff(name, status, amount):
    """Put `amount` of a status on the announced target: Roar, Track,
    Shrinker, Constrict. Targeted, so the player about to get it is shown."""
    def effects(enemy, context):
        if context.target is None:
            return []
        return [status(source=enemy, target=context.target, amount=amount)]
    return Move(name, Move.DEBUFF, effects, targeted=True)


def guard(name, block):
    """Gain Block and nothing else (Crossbow Raider's Reload)."""
    return Move(name, Move.BLOCK,
                lambda enemy, context: [InstantBlock(source=enemy, target=enemy, amount=block)])


def hand_out(card_id, amount=1, pile=InstantAddCard.DISCARD):
    """Effects putting `amount` of a status card into the announced target's
    pile - the discard, as the reference does for Slimed and Infection. Wrap
    in a targeted Move so the player about to be slimed is shown."""
    def effects(enemy, context):
        if context.target is None:
            return []
        return [InstantAddCard(source=enemy, target=context.target,
                               card_id=card_id, pile=pile, amount=amount)]
    return effects


class ScriptedEnemy(Enemy):
    """An enemy that follows a move list: `pick_move(turn)` says which.

    A single-target Attack picks its victim when the intent is chosen, not when
    it lands, so the client can show who is about to be hit. Combat honours
    that pick if the ally is still standing (`_enemy_target`).
    """

    # Base HP is the single-player number; Combat scales it for co-op, and
    # sets block_scale, which the resolver applies to Block this enemy gains.
    CATEGORY = "normal"
    # The wiki gives most enemies a range, "HP 32-35", rolled once per fight.
    # Set this and DEFAULT_MAX_HP / DEFAULT_HP_VARIANCE are not consulted.
    HP_RANGE = None
    # What the client shows. The class name stands in when this is not set.
    NAME = None

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        if max_hp is None and self.HP_RANGE is not None:
            source = rng if rng is not None else random
            max_hp, hp_variance = source.randint(*self.HP_RANGE), 0
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        if self.NAME is not None:
            self.name = self.NAME
        self.turn = 0
        self.move = None
        self.target_id = None
        self.block_scale = 1.0
        # The context of the intent being chosen, for a pick_move that needs
        # the rng (Fogmog) or the fight's counters (a Two-Tailed Rat's budget).
        self.context = None
        # Summoning. `leader` is who called this enemy in; Combat marks a
        # death resolved once on_death has run and any minions have left.
        self.leader = None
        self.death_resolved = False
        # Set by on_death to come back: enemy phases to sit out, then revive.
        self.revive_in = 0

    def pick_move(self, turn):
        raise NotImplementedError

    def on_death(self, context):
        """Effects to resolve as this enemy dies, before the fight can end -
        Phrog Parasite's Wrigglers. Default: an Illusion schedules a revival,
        if the leader who cast it is still standing."""
        if self.get_status("illusion") is not None and (
                self.leader is None or self.leader.is_alive()):
            self.revive_in = 1
        return []

    def revive(self):
        """Back at full HP. Statuses are kept; Combat chooses the next intent
        along with everyone else's."""
        self.current_hp = self.max_hp
        self.block = 0
        self.death_resolved = False
        self.intent = None

    def choose_intent(self, context=None):
        self.context = context
        self.move = self.pick_move(self.turn)
        self.turn += 1
        self.target_id = None
        if self.move.targeted and context is not None:
            living = [a for a in context.all_allies if a.is_alive()]
            if living:
                self.target_id = context.rng.choice(living).unit_id
        self.intent = {
            "type": self.move.kind,
            "name": self.move.name,
            "amount": self.move.damage,
            "hits": self.move.hits,
            "target": self.target_id,
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


def block_scale(player_count, act="act1"):
    # Block scales harder than HP for two players: flat x2, no act factor.
    if player_count <= 1:
        return 1.0
    if player_count == 2:
        return 2.0
    return player_count * ACT_SCALING.get(act, 1.0)
