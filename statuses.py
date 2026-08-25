"""
Status effect definitions for the combat replica.

Each status is a stacking (or non-stacking) counter living on an Entity.
Numbers/behavior are now cross-checked against the real STS2 Buffs wiki
page, which documents two independent axes for every status:

  - stack type: how stacks accumulate / what they mean
      INTENSITY   - effectiveness scales with stack count
      DURATION    - stack count = turns remaining
      COUNTER     - triggers on an event, usually loses 1 stack per trigger
      NONSTACKING - binary on/off, doesn't accumulate

  - turn behavior: what happens to the stacks when a turn boundary passes
      PERMANENT   - untouched by normal turn passage
      CONSERVED   - untouched as the turn passes (same as permanent for
                    our purposes; kept distinct to match wiki terminology)
      DECREMENTED - loses 1 stack as the turn passes
      REMOVED     - wiped to 0 as the turn passes
      CONSUMED    - wiped to 0 the moment it triggers its effect
      RESET       - snaps back to a fixed value (not yet used by any
                    status implemented here)

This replaces the old single `DECAYING_EACH_TURN` set with per-status
metadata, since a flat "everything decays by 1" rule was wrong for most
of the real buffs (many are Permanent, some are Removed/Consumed instead
of Decremented).
"""

from enum import Enum, auto
from typing import Dict, Tuple


class StatusType(Enum):
    # An identity hash instead of Enum's own. Enum.__hash__ is a PYTHON-level
    # method (it returns hash(self._name_)), and this enum is the key type for
    # every status collection in the engine -- Entity.statuses, STATUS_META,
    # DEBUFF_STATUSES, env.py's _FOLDED -- so a lookup as ordinary as
    # `statuses.get(StatusType.WEAK, 0)` pays a Python call just to hash the
    # key. Measured at 51,397 hash calls in a short env run, which was 100% of
    # all enum hashing in this codebase.
    #
    # SAFE because Enum members are per-process singletons and Enum defines no
    # __eq__, so equality is ALREADY identity -- an identity hash is exactly
    # consistent with it, which is the property a hash has to have.
    #
    # Does NOT affect iteration order: every enum-keyed collection here is
    # either a dict (insertion-ordered since 3.7, whatever the hash) or a set
    # used only for membership tests. Nor is cross-process hash stability lost,
    # because Enum's own name-hash is already randomised by PYTHONHASHSEED.
    #
    # Worth +4.5% on env.step. Deliberately NOT applied to this project's five
    # other enums (StackType, TurnBehavior, CardType, TargetMode, IntentType):
    # they are compared with == and never hashed, so it would be cargo cult.
    __hash__ = object.__hash__

    # Debuffs (bad for the holder)
    VULNERABLE = auto()   # take 50% more attack damage
    WEAK = auto()          # deal 25% less attack damage
    FRAIL = auto()         # gain 25% less block
    POISON = auto()        # lose N hp at start of turn, then N -= 1
    SHRINK = auto()         # "Attacks deal 30% less damage. Removed when the applier
                             # dies / after 3 turns." The duration was previously guessed at
                             # ~2 turns from a conflicting source; the debuff module settles
                             # it at 3. The removed-when-the-applier-dies half is NOT modeled
                             # -- nothing tracks which entity applied a given status
    CONSTRICT = auto()      # while the applying enemy (Slithering Strangler) is alive, take
                             # N damage at the end of the holder's turn; N = stack count

    # Buffs (good for the holder)
    STRENGTH = auto()      # + N damage on attacks (flat)
    STRENGTH_THIS_TURN = auto()  # + N damage on attacks, wiped at end of turn (Setup Strike)
    DEXTERITY = auto()     # + N block on block-granting cards (flat)
    DEXTERITY_THIS_TURN = auto()  # + N block on block-granting cards, wiped at end of turn (Speed Potion)
    RITUAL = auto()        # + N strength at start of holder's turn (enemy only, usually)
    METALLICIZE = auto()   # gain N block at end of turn
    PLATED_ARMOR = auto()  # gain N block at end of turn, decays by 1 per turn (see STATUS_META)
    REGEN = auto()         # heal N hp at start of turn, then N -= 1
    SLIPPERY = auto()      # the next N times this entity loses unblocked HP, it loses only 1
                            # HP instead and a stack is spent; a fully-blocked hit spends none
    ARTIFACT = auto()      # negates the next N debuffs applied to this entity; each negation
                            # spends a stack. See DEBUFF_STATUSES and Entity.add_status()
    SKITTISH = auto()      # the first time this entity is hit each turn, it gains N Block.
                            # N is the stack count and is NOT consumed -- the once-per-turn
                            # limit is a per-turn flag on the entity, not stack decay
    THORNS = auto()        # "When hit by an attack, deal X damage back." Fires per HIT, not
                            # per card (contrast SKITTISH above) -- a 3-hit attack eats 3
                            # retaliations. Stacks are never spent. See Entity.take_damage()
    THORNS_THIS_TURN = auto()  # same retaliation, wiped at end of turn (Flame Barrier).
                            # Separate status rather than a flag so it stacks with real
                            # Thorns, mirroring STRENGTH / STRENGTH_THIS_TURN
    VIGOR = auto()         # "Your next Attack deals X additional damage." Consumed by the
                            # next attack (Terror Eel's Thrash). Distinct from the Player-only
                            # next_attack_bonus_damage relic field, which enemies don't have
    INTANGIBLE = auto()     # "Reduce all damage taken and HP loss to 1. Lasts X turns."
                            # (Soul Fysh's Fade)
    RINGING = auto()        # "You can only play 1 card this turn." (Ceremonial Beast)
    SMOGGY = auto()         # "You can only play 1 Skill per turn." (Living Fog)
    STRENGTH_LOSS = auto()  # PERMANENT version of STRENGTH_LOSS_THIS_TURN, for effects that
                            # strip stats outright (Lagavulin Matriarch's Soul Siphon). Same
                            # positive-counter trick: add_status() pops at <=0, so a plain
                            # negative Strength cannot go below zero on its own
    DEXTERITY_LOSS = auto()  # likewise for Dexterity
    STEAM_ERUPTION = auto()  # "When killed, deals X damage at the end of your next turn."
                              # A posthumous bomb, NOT a self-destruct timer -- see the
                              # correction note in README. Every Waterfall Giant move feeds it
    PERSONAL_HIVE = auto()   # "Whenever this enemy is hit by an Attack, add X Dazed into
                              # your Draw Pile." (Entomancer)
    RAVENOUS = auto()        # "When an enemy dies, this creature immediately eats it,
                              # becoming Stunned and gaining X Strength." (Corpse Slug)
    SUCK = auto()            # "Whenever it deals unblocked attack damage, it gains X
                              # Strength." (Fossil Stalker)
    BUFFER = auto()          # "Prevent the next X times you would lose HP." (Lucky Tonic)
    DEXTERITY_LOSS_THIS_TURN = auto()  # turn-scoped mirror of DEXTERITY_LOSS (Tender)
    TENDER = auto()          # "Whenever you play a card, lose X Strength and X Dexterity
                              # this turn." (Hunter Killer). Applied per card play, so the
                              # penalty compounds across a big turn
    BURROWED = auto()        # while burrowed, Block is NOT cleared at the start of the
                              # holder's turn (Tunneler). Not on the Buffs page -- the rule
                              # comes from Tunneler's own page
    FLUTTER = auto()         # takes 50% less Attack damage; each HIT spends one stack, so
                              # it must be hit X times to strip (Thieving Hopper)
    SOAR = auto()            # "Receives 50% less attack damage until it lands."
                              # (Owl Magistrate; its own Verdict move removes it)
    HEX = auto()             # "While Spectral Knight is alive, ALL your cards are Ethereal"
                              # -- i.e. the hand exhausts at end of turn instead of
                              # discarding. Hex IS the Ethereal effect, per the Debuffs page
    DOWNGRADED = auto()      # "While Magi Knight is alive, ALL your cards are Downgraded."
                              # Not documented anywhere; read here as "cards resolve as
                              # their un-upgraded printing" -- see enemies.py make_magi_knight
    SANDPIT = auto()         # "In X turns, you will be eaten and die." A countdown on the
                              # PLAYER: ticks down each of their turns and kills at 0. The
                              # Frantic Escape status card pushes it back up
    PLOW = auto()            # Ceremonial Beast phase marker: "the first time this enemy's HP
                              # reaches X or below, it becomes Stunned and loses all Strength".
                              # Stacks hold X (the HP threshold), not an intensity
    STRENGTH_LOSS_THIS_TURN = auto()  # subtracts from outgoing attack damage, wiped at end
                            # of turn (Mangle: "enemy loses N Strength this turn"). Stored
                            # as a POSITIVE counter representing a loss, because
                            # add_status() pops any status at <=0 and so cannot hold a
                            # negative -- the exact blocker that kept Mangle unported

    # Real STS2 multiplayer statuses (from the Tank card)
    TANK_SELF = auto()     # take 50% additional damage from enemies
    TANK_ALLY = auto()     # take 50% LESS damage from enemies (granted by an ally's Tank)

    # Co-op specific glue (placeholder for future link/lane mechanics)
    LINKED = auto()        # marks that this entity shares link charge this turn

    # Real STS2 debuff, NOT yet wired to any effect: attacks cost 1 additional
    # energy for 2 turns. Needs the dynamic-cost-modifier system (see the
    # "Known gaps" list in README.md) before it can do anything; the
    # StatusType exists so a future card/enemy move can apply it without
    # another statuses.py change.
    TANGLED = auto()


class StackType(Enum):
    INTENSITY = auto()
    DURATION = auto()
    COUNTER = auto()
    NONSTACKING = auto()


class TurnBehavior(Enum):
    PERMANENT = auto()
    CONSERVED = auto()
    DECREMENTED = auto()
    REMOVED = auto()
    CONSUMED = auto()
    RESET = auto()


# Per-status metadata, cross-checked against the real STS2 Buffs page where
# a matching status exists. Statuses that tick via their own start-of-turn
# effect (Poison, Regen) are marked PERMANENT here because the generic
# end-of-turn decay does NOT touch them -- their own tick_start_of_turn
# logic in entities.py decrements them after firing.
STATUS_META: Dict[StatusType, Tuple[StackType, TurnBehavior]] = {
    StatusType.VULNERABLE: (StackType.DURATION, TurnBehavior.DECREMENTED),
    StatusType.WEAK: (StackType.DURATION, TurnBehavior.DECREMENTED),
    StatusType.FRAIL: (StackType.DURATION, TurnBehavior.DECREMENTED),
    StatusType.POISON: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    # Duration, not Nonstacking: the module gives it a 3-turn life, so the
    # stack count has to mean turns remaining for that to decay correctly.
    StatusType.SHRINK: (StackType.DURATION, TurnBehavior.DECREMENTED),
    StatusType.CONSTRICT: (StackType.INTENSITY, TurnBehavior.CONSERVED),
    StatusType.STRENGTH: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.STRENGTH_THIS_TURN: (StackType.INTENSITY, TurnBehavior.REMOVED),
    StatusType.DEXTERITY: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.DEXTERITY_THIS_TURN: (StackType.INTENSITY, TurnBehavior.REMOVED),
    StatusType.RITUAL: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.METALLICIZE: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.PLATED_ARMOR: (StackType.INTENSITY, TurnBehavior.DECREMENTED),
    StatusType.REGEN: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.SLIPPERY: (StackType.COUNTER, TurnBehavior.CONSUMED),
    StatusType.ARTIFACT: (StackType.COUNTER, TurnBehavior.CONSERVED),
    # Wiki calls Skittish a Counter, but its stacks are the BLOCK AMOUNT and
    # are never spent -- PERMANENT here so the generic decay leaves them
    # alone. "First time each turn" is enforced by Enemy.skittish_used_this_turn.
    StatusType.SKITTISH: (StackType.COUNTER, TurnBehavior.PERMANENT),
    # Intensity/Permanent per the wiki.gg Buffs page. One third-party site
    # (spire-codex) calls Thorns a Counter, which would imply stacks are
    # spent per trigger; wiki.gg is treated as authoritative here, same call
    # as the co-op-revive conflict noted in README's source-reliability note.
    # Toadpole's own "Spike Spit" move removing 2 Thorns from itself only
    # makes sense if triggering does NOT spend stacks.
    StatusType.THORNS: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.THORNS_THIS_TURN: (StackType.INTENSITY, TurnBehavior.REMOVED),
    StatusType.STRENGTH_LOSS_THIS_TURN: (StackType.INTENSITY, TurnBehavior.REMOVED),
    # Conserved, not decremented: Vigor is spent by attacking, not by time.
    StatusType.VIGOR: (StackType.INTENSITY, TurnBehavior.CONSERVED),
    StatusType.INTANGIBLE: (StackType.DURATION, TurnBehavior.DECREMENTED),
    StatusType.RINGING: (StackType.DURATION, TurnBehavior.DECREMENTED),
    StatusType.SMOGGY: (StackType.DURATION, TurnBehavior.DECREMENTED),
    StatusType.STRENGTH_LOSS: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.DEXTERITY_LOSS: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.STEAM_ERUPTION: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.PERSONAL_HIVE: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.RAVENOUS: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.SUCK: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.PLOW: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    # Counter/Conserved: spent by triggering, never by time passing.
    StatusType.BUFFER: (StackType.COUNTER, TurnBehavior.CONSERVED),
    StatusType.DEXTERITY_LOSS_THIS_TURN: (StackType.INTENSITY, TurnBehavior.REMOVED),
    StatusType.TENDER: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.BURROWED: (StackType.NONSTACKING, TurnBehavior.PERMANENT),
    StatusType.FLUTTER: (StackType.COUNTER, TurnBehavior.CONSERVED),
    # Deliberately PERMANENT: the countdown is driven by CombatEngine, not by
    # the generic decay, so the two can't both tick it.
    StatusType.SANDPIT: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.SOAR: (StackType.NONSTACKING, TurnBehavior.PERMANENT),
    # Both last exactly as long as the knight granting them, so neither
    # decays on its own -- the enemy's death effect clears them.
    StatusType.HEX: (StackType.INTENSITY, TurnBehavior.PERMANENT),
    StatusType.DOWNGRADED: (StackType.NONSTACKING, TurnBehavior.PERMANENT),
    StatusType.TANK_SELF: (StackType.NONSTACKING, TurnBehavior.PERMANENT),
    StatusType.TANK_ALLY: (StackType.NONSTACKING, TurnBehavior.PERMANENT),
    StatusType.LINKED: (StackType.NONSTACKING, TurnBehavior.REMOVED),
    StatusType.TANGLED: (StackType.DURATION, TurnBehavior.DECREMENTED),
}


# Which statuses count as "a debuff" for Artifact's "negates X debuffs".
# statuses.py grouped buffs and debuffs by COMMENT only until Artifact needed
# the distinction programmatically. Deliberately excludes TANK_SELF: it reads
# like a debuff (take 50% more damage) but a player applies it to THEMSELVES
# on purpose via the Tank card, and having Artifact silently eat it would be
# wrong.
DEBUFF_STATUSES = frozenset({
    StatusType.VULNERABLE,
    StatusType.WEAK,
    StatusType.FRAIL,
    StatusType.POISON,
    StatusType.SHRINK,
    StatusType.CONSTRICT,
    StatusType.TANGLED,
    StatusType.RINGING,
    StatusType.SMOGGY,
    StatusType.STRENGTH_LOSS,
    StatusType.DEXTERITY_LOSS,
    StatusType.STRENGTH_LOSS_THIS_TURN,
    StatusType.DEXTERITY_LOSS_THIS_TURN,
    StatusType.TENDER,
    StatusType.SANDPIT,
    StatusType.HEX,
    StatusType.DOWNGRADED,
})


def net_strength(statuses: dict) -> int:
    """Effective Strength: the number the rules actually use.

    Four statuses feed one value. Strength is permanent, Strength-this-turn
    is wiped at end of turn, and the two LOSS counters are stored as POSITIVE
    numbers that subtract -- add_status() pops anything at <=0, so a negative
    Strength cannot be held on top of a positive one, which is the whole
    reason the loss variants exist as separate statuses.

    Lives here beside the multiplier helpers, and takes the statuses dict
    rather than an Entity, because that is the shape the rest of this module
    already uses -- and because env.py needs it for an OBSERVATION, where
    there is no reason to reach through an entity.

    Three copies of this sum existed (deal_attack_damage, gain_block's
    dexterity twin, and env's _status_features). A four-term formula split
    across two modules is exactly the kind of thing that drifts by one term
    and then quietly reports a different number to the agent than the engine
    is using."""
    return (statuses.get(StatusType.STRENGTH, 0)
            + statuses.get(StatusType.STRENGTH_THIS_TURN, 0)
            - statuses.get(StatusType.STRENGTH_LOSS, 0)
            - statuses.get(StatusType.STRENGTH_LOSS_THIS_TURN, 0))


def net_dexterity(statuses: dict) -> int:
    """Effective Dexterity, the exact mirror of net_strength()."""
    return (statuses.get(StatusType.DEXTERITY, 0)
            + statuses.get(StatusType.DEXTERITY_THIS_TURN, 0)
            - statuses.get(StatusType.DEXTERITY_LOSS, 0)
            - statuses.get(StatusType.DEXTERITY_LOSS_THIS_TURN, 0))


def damage_multiplier_for_attacker(statuses: dict) -> float:
    """Multiplier applied to outgoing attack damage based on the attacker's own statuses."""
    mult = 1.0
    if statuses.get(StatusType.WEAK, 0) > 0:
        mult *= 0.75
    if statuses.get(StatusType.SHRINK, 0) > 0:
        mult *= 0.7
    return mult


def damage_multiplier_for_defender(statuses: dict, vulnerable_bonus: float = 0.0) -> float:
    """Multiplier applied to incoming attack damage based on the defender's
    own statuses.

    vulnerable_bonus comes from the ATTACKER (the Cruelty card, the Paper
    Phrog relic) and is ADDITIVE with Vulnerable's own 50%, not applied on
    top of it. Paper Phrog's text settles the ambiguity: "enemies with
    Vulnerable take 75% more damage rather than 50%" -- 1.5 + 0.25, not
    1.5 x 1.25."""
    mult = 1.0
    if statuses.get(StatusType.VULNERABLE, 0) > 0:
        mult *= 1.5 + vulnerable_bonus
    if statuses.get(StatusType.TANK_SELF, 0) > 0:
        mult *= 1.5
    if statuses.get(StatusType.TANK_ALLY, 0) > 0:
        mult *= 0.5
    return mult


def block_multiplier(statuses: dict) -> float:
    mult = 1.0
    if statuses.get(StatusType.FRAIL, 0) > 0:
        mult *= 0.75
    return mult
