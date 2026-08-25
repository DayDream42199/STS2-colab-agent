"""
Entity model: shared base for Player and Enemy, handling HP, block,
statuses, and damage resolution in one place so combat.py doesn't
duplicate rules.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import random

from statuses import (
    StatusType,
    StackType,
    TurnBehavior,
    STATUS_META,
    DEBUFF_STATUSES,
    damage_multiplier_for_attacker,
    damage_multiplier_for_defender,
    block_multiplier,
    net_strength,
    net_dexterity,
)


# "The maximum number of cards allowed in hand is 10. There is no way to
# exceed this limit." -- the wiki's Mechanics page. Nothing enforced this
# until now, so a Retain deck could hold an arbitrarily large hand and every
# card-generating effect could stack past 10.
#
# SOURCE CAVEAT: that Mechanics page is the STS1 one -- the wiki has no STS2
# equivalent -- so this is an STS1 rule applied to an STS2 replica. It is
# also the number env.py has assumed in MAX_HAND since it was written.
#
# WHERE THE OVERFLOW GOES: the same page says drawn excess goes to the
# DISCARD pile but created excess goes to the DRAW pile. That second half is
# contradicted by eight individual card pages (Blade Dance, Cloak and
# Dagger, Deus Ex Machina, Dual Wield, Nightmare, Power Through, Hello
# World, Magnetism), each of which says "it gets added to the discard pile".
# Eight specific pages beat one general clause, so everything overflows to
# the discard pile here.
HAND_LIMIT = 10


# ---------------------------------------------------------------------------
# Content RNG: everything rolled while BUILDING a fight, before any engine
# exists to own a seed -- the HP in enemies.py's 47 make_*() factories, and
# each Player's own rng below.
#
# It lives here rather than in enemies.py because enemies.py imports this
# module, so this is the only end of that edge that both can reach.
#
# WHY IT EXISTS. Those rolls used the global `random` module, which nothing
# in the engine seeds, so CombatEnv(seed=N).reset() fought a different enemy
# every time: no episode replay, no fixed-seed A/B between policies, no
# reproducing a specific fight to debug it. A CombatEngine seed cannot reach
# them -- a factory runs before any engine exists -- which is why this is a
# module global rather than a parameter threaded through 103 factory
# signatures.
#
# Seeding is the DRIVER's job (env.reset, bench.run_encounter, tools/), since
# only the driver knows when an episode begins and must seed BEFORE building.
#
# An unseeded random.Random() takes its state from system entropy exactly as
# the global module does, so a caller that never touches seed_content() --
# play.py, demo.py -- behaves precisely as it did before.
#
# LIMIT: one stream per process, so two envs whose reset() calls interleave
# would share it. That cannot happen in single-threaded Python (a reset runs
# its factories synchronously) and does not happen across subprocesses, which
# get their own module. It WOULD happen with threaded vectorised envs.
CONTENT_RNG = random.Random()


def seed_content(seed: Optional[int] = None):
    """Reseed the construction-time rng. Call BEFORE building a fight.

    seed=None reseeds from system entropy, i.e. deliberately back to
    unreproducible -- the way to opt a driver out again."""
    CONTENT_RNG.seed(seed)


@dataclass
class DamageResult:
    raw: int
    to_block: int
    to_hp: int
    killed: bool


class Entity:
    # ---- defaults for the fields only ONE subclass actually owns ----------
    # Player and Enemy each carry state the other does not, but the damage
    # and block code below is shared and reads both sides. That used to mean
    # 20 getattr/hasattr guards scattered through the hottest methods in the
    # engine: they hid which fields exist, made shared code read as though it
    # were probing an unknown object, and paid a lookup-with-fallback per
    # attack.
    #
    # The guards that REMAIN in this file are a different thing and are meant
    # to stay: hasattr(x, "fire_hook") / "draw_pile" / "discard_pile" ask
    # "is this side a Player?" -- a capability question, not a missing field
    # with an obvious default.
    #
    # Declaring the defaults here means a plain `self.field` works on both
    # sides, and this block doubles as the inventory of what the shared code
    # is allowed to read. Each subclass still sets its own in __init__; these
    # are only the value the OTHER side sees.
    #
    # EVERY DEFAULT HERE MUST BE IMMUTABLE. A class attribute is one object
    # shared by every instance, so a mutable default would be shared state
    # for the whole fight -- `attacked_by_this_turn = []` would mean appending
    # a Gang Up attacker to one enemy appended it to all twelve. The two
    # collection-valued fields below are therefore declared as None and (),
    # and their real containers are built per instance in the subclass.

    # Player-side, read by the shared damage/block code
    no_card_block_turns = 0               # Panic Button
    next_attack_bonus_damage = 0          # Akabeko
    next_attack_double = False            # Pen Nib
    next_attack_multiplier = 1            # Gigantification Potion
    card_damage_bonus = 0                 # Strike Dummy, Miniature Cannon
    bonus_strength_below_half = 0         # Red Skull
    flat_damage_reduction = 0             # Tungsten Rod
    vulnerable_damage_bonus = 0.0         # Cruelty, Paper Phrog
    vulnerable_attacker_reduction = 0.0   # Colossus
    redirect_attacks_from = ()            # Intercept -- tuple, not list
    engine = None                         # set by CombatEngine.__init__

    # Enemy-side, read by the shared damage code
    attacked_by_this_turn = None   # Gang Up. None means "no such list here";
                                   # Enemy.__init__ builds the real one
    knockdown = None               # (caster, multiplier)
    invulnerable = False           # Waterfall Giant while it charges
    painful_stabs = 0              # Test Subject phase 2
    hit_by_current_card = False    # Skittish bookkeeping
    stunned_turns = 0              # skips this many of its own turns

    def __init__(self, name: str, max_hp: int):
        self.name = name
        self.max_hp = max_hp
        self.hp = max_hp
        self.block = 0
        self.statuses: Dict[StatusType, int] = {}
        self.alive = True

    # ---------- status helpers ----------
    def add_status(self, status: StatusType, amount: int = 1, applier: "Entity" = None):
        """applier is who is APPLYING the status, and exists for powers that
        read "whenever YOU apply X" (Vicious). The pre-existing
        `status_gained` hook fires on the RECEIVER, which is the wrong side
        for those, and there was no way to tell "the enemy gained Vulnerable
        because I applied it" from "because a teammate did". Optional, so
        the many call sites that don't care are unaffected."""
        if amount == 0:
            return
        # Artifact: "Negates X debuffs." Intercepts BEFORE the status lands,
        # spending one Artifact stack instead. Only positive applications of a
        # real debuff are negated -- a negative amount is a decay/removal step
        # (decay_statuses_end_of_turn calls add_status(s, -1)) and must pass
        # through, or debuffs the holder already has could never wear off.
        if (amount > 0 and status in DEBUFF_STATUSES
                and self.statuses.get(StatusType.ARTIFACT, 0) > 0):
            self.statuses[StatusType.ARTIFACT] -= 1
            if self.statuses[StatusType.ARTIFACT] <= 0:
                self.statuses.pop(StatusType.ARTIFACT, None)
            return
        self.statuses[status] = self.statuses.get(status, 0) + amount
        if self.statuses[status] <= 0:
            self.statuses.pop(status, None)
        elif amount > 0 and hasattr(self, "fire_hook"):
            self.fire_hook("status_gained", status=status, amount=amount)
        if amount > 0 and applier is not None and hasattr(applier, "fire_hook"):
            applier.fire_hook("status_applied", status=status, amount=amount,
                              target=self)

    def get_status(self, status: StatusType) -> int:
        return self.statuses.get(status, 0)

    def has_status(self, status: StatusType) -> bool:
        return self.get_status(status) > 0

    def decay_statuses_end_of_turn(self):
        """Apply each status's real turn-boundary behavior (see statuses.py)
        instead of one flat decay rule. PERMANENT/CONSERVED statuses are
        untouched; DECREMENTED lose 1 stack; REMOVED wipe to 0. CONSUMED
        statuses are cleared at the point they trigger, not here."""
        for s in list(self.statuses.keys()):
            _, behavior = STATUS_META.get(s, (StackType.INTENSITY, TurnBehavior.PERMANENT))
            if behavior == TurnBehavior.DECREMENTED:
                self.add_status(s, -1)
            elif behavior == TurnBehavior.REMOVED:
                self.statuses.pop(s, None)
            # PERMANENT, CONSERVED, CONSUMED, RESET: no generic action here

    def tick_start_of_turn(self, log: Optional[list] = None):
        """Start-of-turn statuses. Only Poison lives here.

        Regen and Ritual USED to tick here too, which was wrong:
        Module:Powers/StS2_data/Common defines both as END of turn --
        Regen "at the end of your turn, heal X HP, then reduce Regen by 1"
        and Ritual "at the end of its turn, gains X Strength". Poison is
        the one that really is start-of-turn: "at the start of its turn,
        loses X HP, then reduce Poison by 1"."""
        if self.get_status(StatusType.POISON) > 0:
            n = self.get_status(StatusType.POISON)
            self.take_damage(n, source_is_attack=False, log=log, label="poison")
            self.add_status(StatusType.POISON, -1)

    def apply_end_of_turn_gains(self, log: Optional[list] = None):
        """Everything the powers module defines as happening at end of turn:
        Metallicize/Plating block, then Regen, then Ritual."""
        gain = 0
        if self.get_status(StatusType.METALLICIZE) > 0:
            gain += self.get_status(StatusType.METALLICIZE)
        if self.get_status(StatusType.PLATED_ARMOR) > 0:
            gain += self.get_status(StatusType.PLATED_ARMOR)
        if gain:
            self.gain_block(gain, from_card=False)
            if log is not None:
                log.append(f"{self.name} gains {gain} block (metallicize/plated armor)")
        if self.get_status(StatusType.REGEN) > 0:
            n = self.get_status(StatusType.REGEN)
            before = self.hp
            self.heal(n)
            self.add_status(StatusType.REGEN, -1)
            if log is not None:
                log.append(f"{self.name} heals {self.hp - before} HP (Regen)")
        if self.get_status(StatusType.RITUAL) > 0:
            n = self.get_status(StatusType.RITUAL)
            self.add_status(StatusType.STRENGTH, n)
            if log is not None:
                log.append(f"{self.name} gains {n} Strength (Ritual)")

    # ---------- combat actions ----------
    def gain_block(self, amount: int, from_card: bool = True):
        """`from_card` distinguishes Block granted BY A CARD from Block
        granted by a relic, potion or end-of-turn power, because Panic
        Button ("You cannot gain Block from cards for 2 turns") only stops
        the former. It defaults to True since card effects are the large
        majority of callers; relics, potions and Metallicize/Plating pass
        False. Read with getattr so Enemy, which shares this method but has
        no such field, is unaffected.

        Dexterity was tracked as a status since early in this project
        (comment: '+N block on block-granting cards') but never actually
        consulted here -- a real pre-existing gap, found while cross-
        referencing for potions.py's Speed Potion. Applied as a flat add,
        mirroring how Strength adds flat damage before Weak's multiplier
        in deal_attack_damage -- Frail's multiplier applies after, same
        relative order."""
        if from_card and self.no_card_block_turns > 0:
            return 0
        dex = net_dexterity(self.statuses)
        mult = block_multiplier(self.statuses)
        gained = max(0, round((amount + dex) * mult))
        self.block += gained
        if gained and hasattr(self, "fire_hook"):
            self.fire_hook("block_gained", amount=gained)
        return gained

    def gain_block_noncard(self, amount: int):
        """Block from a relic, potion or power. Named rather than requiring
        every one of those call sites to remember `from_card=False`, since
        forgetting it there is a silent Panic Button bug."""
        return self.gain_block(amount, from_card=False)

    def clear_block(self):
        self.block = 0

    def deal_attack_damage(self, base_amount: int) -> int:
        """Compute outgoing damage from THIS entity as attacker, applying
        strength and weak. Does not apply the defender's vulnerable — that
        happens on the receiving side in take_damage.

        next_attack_bonus_damage / next_attack_double are generic, relic-
        driven, "consumed by the next attack" modifiers (Akabeko's Vigor,
        Pen Nib's every-10th-attack-doubles) -- Enemy instances don't have
        these fields, hence getattr defaults, mirroring the hasattr guards
        used elsewhere in this class for Player-only features."""
        # Strength, Strength-this-turn and the two positive-counter LOSS
        # statuses (Mangle, Soul Siphon) all fold into one number -- see
        # statuses.net_strength for why the losses are stored positive.
        amount = base_amount + net_strength(self.statuses)
        # Vigor: "your next Attack deals X additional damage", then it's gone.
        # Spent here rather than decayed on a turn boundary, matching its
        # Conserved turn behavior on the wiki.
        vigor = self.get_status(StatusType.VIGOR)
        if vigor:
            amount += vigor
            self.statuses.pop(StatusType.VIGOR, None)
        amount += self.next_attack_bonus_damage
        amount += self.card_damage_bonus
        # Red Skull: "while your HP is at or below 50%, you have 3
        # additional Strength." Conditional, so it is recomputed per attack
        # rather than added and removed as the HP crosses the line.
        below_half = self.bonus_strength_below_half
        if below_half and self.hp * 2 <= self.max_hp:
            amount += below_half
        amount = amount * damage_multiplier_for_attacker(self.statuses)
        if self.next_attack_double:
            amount *= 2
        # Generalized version of the above, for effects that aren't exactly
        # "double" (Gigantification Potion triples). Kept separate from
        # next_attack_double so Pen Nib and a potion can both apply.
        mult = self.next_attack_multiplier
        if mult != 1:
            amount *= mult
            self.next_attack_multiplier = 1
        # Guarded on the value, not on hasattr: both now have a class default,
        # so an unconditional write would create an instance attribute on every
        # enemy that ever swings, just to store the zero it already reads.
        if self.next_attack_bonus_damage:
            self.next_attack_bonus_damage = 0
        if self.next_attack_double:
            self.next_attack_double = False
        return max(0, round(amount))

    def take_damage(self, raw_amount: int, source_is_attack: bool = True,
                     log: Optional[list] = None, label: str = "attack",
                     attacker: Optional["Entity"] = None) -> DamageResult:
        """attacker is who is swinging, and exists solely so Thorns can hit
        back. It defaults to None, which means "no retaliation" -- that is
        the correct behavior for every damage source that is not a creature
        attacking (poison, Constrict, Infection, and the relic/potion damage
        in relics.py/potions.py, which pass source_is_attack=False anyway).
        Card effects pass their caster, enemy moves pass the enemy."""
        amount = raw_amount
        if source_is_attack and attacker is not None:
            # Gang Up counts "each time another player has attacked the enemy
            # this turn", so the defender records its attackers. Guarded with
            # getattr because only Enemy keeps this list.
            seen = self.attacked_by_this_turn
            if seen is not None:
                seen.append(attacker)
            # Knockdown: "The enemy takes double/triple damage from OTHER
            # players this turn." Stored on the victim as (caster, mult) so
            # the caster's own hits are excluded.
            kd = self.knockdown
            if kd is not None and attacker is not kd[0]:
                amount *= kd[1]
        if source_is_attack:
            # Cruelty (card) and Paper Phrog (relic) raise the attacker's
            # Vulnerable multiplier; it is folded into the defender
            # calculation because it is ADDITIVE with Vulnerable's own 50%,
            # not a second multiplier on top of it.
            vuln_bonus = attacker.vulnerable_damage_bonus if attacker else 0.0
            amount = amount * damage_multiplier_for_defender(self.statuses, vuln_bonus)
            # Colossus is the mirror: less damage FROM a Vulnerable attacker.
            if attacker is not None and attacker.get_status(StatusType.VULNERABLE) > 0:
                amount *= 1.0 - self.vulnerable_attacker_reduction
        amount = max(0, round(amount))
        reduction = self.flat_damage_reduction
        if reduction and amount > 0:
            amount = max(0, amount - reduction)
        # Soar: "receives 50% less attack damage until it lands." Unlike
        # Flutter this spends nothing -- only the holder's own landing move
        # (Owl Magistrate's Verdict) removes it.
        if source_is_attack and self.get_status(StatusType.SOAR) > 0:
            amount = amount * 0.5
        # Flutter: "takes 50% less Attack damage; must be hit X times.
        # Each HIT spends a stack whether or not it got through, which is
        # what makes multi-hit cards the answer to it.
        if source_is_attack and self.get_status(StatusType.FLUTTER) > 0:
            amount = amount * 0.5
            self.add_status(StatusType.FLUTTER, -1)
            # "Deal attack damage X times to Stun it" -- running the counter
            # out doesn't just remove the buff, it stuns the holder.
            if self.get_status(StatusType.FLUTTER) <= 0:
                self.stunned_turns = max(self.stunned_turns, 1)
                if log is not None:
                    log.append(f"{self.name} is stunned (Flutter broken)")
        amount = max(0, round(amount))
        # Intangible caps EVERYTHING at 1, so it is applied last, after every
        # other multiplier and reduction. Also honored in lose_hp().
        if amount > 0 and self.get_status(StatusType.INTANGIBLE) > 0:
            amount = 1
        # Waterfall Giant's "About To Blow" makes it untouchable while it
        # charges. A plain flag rather than a status: it is a scripted boss
        # phase, not something that can be applied, stacked, or dispelled.
        if self.invulnerable:
            amount = 0

        # Skittish reacts to being HIT, blocked or not, and fires once per
        # card rather than once per hit -- so the flag is set here and read
        # after the whole card resolves (CombatEngine.resolve_card_effect).
        # Only _resolve_skittish reads it, and only off enemies, so setting it
        # on a Player is harmless and saves branching on which side we are.
        if source_is_attack and amount > 0:
            self.hit_by_current_card = True

        absorbed = min(self.block, amount)
        self.block -= absorbed
        remainder = amount - absorbed
        # Buffer: "prevent the next X times you would lose HP". Checked
        # before Slippery, since a prevented hit never becomes HP loss at
        # all and so shouldn't also spend a Slippery stack.
        if remainder > 0 and self.get_status(StatusType.BUFFER) > 0:
            self.add_status(StatusType.BUFFER, -1)
            if log is not None:
                log.append(f"{self.name} prevents the HP loss (Buffer)")
            remainder = 0
        if remainder > 0 and self.get_status(StatusType.SLIPPERY) > 0:
            # "The next N times this creature loses HP, it only loses 1 HP
            # instead" -- a fully-blocked hit (remainder == 0) spends no
            # stack, matching the wiki's "no longer loses a stack when
            # fully blocking a hit" fix note.
            self.add_status(StatusType.SLIPPERY, -1)
            remainder = 1
        self.hp -= remainder
        killed = False
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            killed = True
        if log is not None:
            log.append(
                f"{self.name} takes {amount} {label} dmg ({absorbed} blocked, {remainder} to hp)"
                + (" -- DIES" if killed else "")
            )
        if remainder and hasattr(self, "fire_hook"):
            self.fire_hook("hp_lost", amount=remainder, source="attack")
        # Personal Hive (Entomancer): "whenever this enemy is hit by an
        # Attack, add X Dazed into your Draw Pile."
        hive = self.get_status(StatusType.PERSONAL_HIVE)
        if hive and source_is_attack and amount > 0 and attacker is not None \
                and hasattr(attacker, "draw_pile"):
            from cards import make_dazed
            for _ in range(hive):
                attacker.draw_pile.insert(0, make_dazed())
            if log is not None:
                log.append(f"{attacker.name} gains {hive} Dazed (Personal Hive)")
        # Suck (Fossil Stalker): "whenever it deals UNBLOCKED attack damage,
        # it gains X Strength" -- read off the attacker, not the defender.
        if attacker is not None and source_is_attack and remainder > 0:
            suck = attacker.get_status(StatusType.SUCK)
            if suck:
                attacker.add_status(StatusType.STRENGTH, suck)
                if log is not None:
                    log.append(f"{attacker.name} gains {suck} Strength (Suck)")
        # Painful Stabs (Test Subject phase 2): "adds Wounds to the attacker's
        # discard pile when it takes UNBLOCKED damage". A plain attribute
        # rather than a status: it is a scripted boss power, not something
        # that can be applied or dispelled.
        stabs = self.painful_stabs
        if stabs and remainder > 0 and attacker is not None and hasattr(attacker, "discard_pile"):
            from cards import make_wound
            for _ in range(stabs):
                attacker.discard_pile.append(make_wound())
            if log is not None:
                log.append(f"{attacker.name} gains {stabs} Wound (Painful Stabs)")
        self._retaliate_thorns(amount, source_is_attack, attacker, log)
        return DamageResult(raw=raw_amount, to_block=absorbed, to_hp=remainder, killed=killed)

    def _retaliate_thorns(self, amount: int, source_is_attack: bool,
                           attacker: Optional["Entity"], log: Optional[list] = None):
        """Thorns: "When hit by an attack, deal X damage back."

        Fires per HIT, not per card -- the opposite of Skittish, which the
        wiki explicitly resolves once per card. A 3-hit attack into 2 Thorns
        therefore costs the attacker 6, which is exactly the trap Toadpole's
        3-hit Spike Spit is built around.

        Three deliberate readings of "when hit", none of them free choices:
        - A FULLY BLOCKED hit still retaliates. The wording is "when hit",
          not "when you lose HP" (contrast Slippery, which the wiki patched
          specifically so a fully-blocked hit spends no stack).
        - A KILLING hit still retaliates -- the attack landed before the
          defender died, so `self.alive` is deliberately not checked.
        - Retaliation damage is NOT an attack (source_is_attack=False), so
          it ignores Strength/Weak/Vulnerable, and cannot trigger the
          attacker's own Thorns back. That last part is what makes two
          Thorns creatures hitting each other terminate instead of
          recursing forever.

        Block DOES absorb the retaliation, matching every other
        source_is_attack=False damage in this replica (poison, Constrict,
        Kusarigama, Parrying Shield). The STS2 wiki doesn't state this
        either way -- flagged in README's known gaps as unverified."""
        if not (source_is_attack and amount > 0 and attacker is not None):
            return
        if attacker is self or not attacker.alive:
            return
        thorns = (self.get_status(StatusType.THORNS)
                  + self.get_status(StatusType.THORNS_THIS_TURN))
        if thorns > 0:
            attacker.take_damage(thorns, source_is_attack=False, log=log,
                                 label=f"Thorns ({self.name})")

    def heal(self, amount: int):
        self.hp = min(self.max_hp, self.hp + amount)

    def lose_hp(self, amount: int, log: Optional[list] = None, label: str = "hp loss") -> int:
        """Direct HP loss that ignores Block entirely -- matches real STS2
        card wording like 'Lose 2 HP', as opposed to take_damage (an
        attack/poison hit, which Block can absorb). Returns the amount
        actually lost. Player overrides this to also track
        lost_hp_this_turn, since several real cards key off that."""
        amount = max(0, amount)
        reduction = self.flat_damage_reduction
        if reduction and amount > 0:
            amount = max(0, amount - reduction)
        if amount > 0 and self.get_status(StatusType.INTANGIBLE) > 0:
            amount = 1   # "...and HP loss to 1"
        if self.invulnerable:
            amount = 0
        if amount > 0 and self.get_status(StatusType.BUFFER) > 0:
            self.add_status(StatusType.BUFFER, -1)
            if log is not None:
                log.append(f"{self.name} prevents the HP loss (Buffer)")
            amount = 0
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
        if log is not None:
            log.append(f"{self.name} loses {amount} hp ({label})")
        if amount and hasattr(self, "fire_hook"):
            self.fire_hook("hp_lost", amount=amount, source="self")
        return amount


class Player(Entity):
    def __init__(self, name: str, max_hp: int, max_energy: int, deck: list):
        super().__init__(name, max_hp)
        self.max_energy = max_energy
        self.energy = max_energy
        self.deck_template = list(deck)   # list of Card
        self.draw_pile = []
        self.hand = []
        self.discard_pile = []
        self.exhaust_pile = []
        # Derived from the content stream, NOT from system entropy. start_combat()
        # reseeds this from the engine seed, so in-combat draws were always
        # reproducible -- but anything drawing BEFORE that was not, and two
        # relics do exactly that: War Paint and Whetstone upgrade random cards
        # in on_pickup, and bench.run_encounter grants relics to a freshly
        # built Player before the engine exists. That left the benchmark
        # deterministic within a process but not across processes.
        self.rng = random.Random(CONTENT_RNG.getrandbits(64))
        # Per-turn trackers that real STS2 cards read (Evil Eye, Forgotten
        # Ritual, Tear Asunder, Battle Trance, etc.). Reset in start_turn().
        self.exhausted_this_turn = []
        self.lost_hp_this_turn = 0
        self.no_more_draw_this_turn = False
        # Per-combat tracker (does NOT reset each turn; combat.py also keeps
        # a combat-wide total across all players for "by ANYONE" cards).
        self.lost_hp_this_combat = 0
        # COUNT of self-inflicted (lose_hp) HP-loss events this combat, as
        # opposed to lost_hp_this_combat's total AMOUNT -- Tear Asunder
        # needs "how many times", not "how many points". Matches
        # lost_hp_this_combat's self-only scope (attack damage from
        # enemies doesn't go through Player.lose_hp).
        self.hp_loss_events_this_combat = 0
        self.retain_block = False   # Barricade: Block isn't cleared at start of turn
        # id(card) for cards whose persistent listener is already registered
        # this combat. A card that registers a combat-long hook (Drum of
        # Battle) can be played more than once per fight -- it goes to the
        # discard pile, gets reshuffled, and is played again -- and without
        # this guard each play stacked ANOTHER listener, so one later
        # trigger paid out once per play instead of once. Per-combat, reset
        # in start_combat() alongside the hooks dict it guards.
        self.armed_card_hooks = set()
        self.acted_this_turn = False
        self.engine = None   # set by CombatEngine.__init__ so hooks can reach it
        # event -> list of (callback, expires_this_turn). callback signature:
        # callback(engine, player, **event_data) -> None
        self.hooks: Dict[str, List] = {}
        # Persistent across the whole run (NOT reset in start_combat, unlike
        # everything above) -- list of Relic. See relics.py.
        self.relics: List = []
        # Generic relic-driven state, all read/written directly by relics.py
        # effect functions rather than needing bespoke Player fields per
        # relic. relic_counters persists for the whole run (e.g. Book of
        # Five Rings' "every 5 cards added" count, Lizard Tail's one-time-
        # ever flag); the rest are per-combat and get reset in start_combat().
        self.relic_counters: Dict[str, int] = {}
        self.pending_relic_block = 0
        self.pending_relic_draw = 0
        self.pending_relic_energy = 0
        self.flat_damage_reduction = 0
        self.next_attack_bonus_damage = 0
        self.next_attack_double = False
        # Per-CARD damage bonus, set for the duration of one card's
        # resolution so it applies to every hit of a multi-hit card
        # (Strike Dummy, Miniature Cannon). next_attack_bonus_damage is
        # consumed by the first hit, which is the wrong shape for these.
        self.card_damage_bonus = 0
        self.bonus_strength_below_half = 0   # Red Skull
        self.retain_block_cap = 0            # Sturdy Clamp
        self.conserve_energy = False         # Ice Cream
        # Potion inventory -- persistent across the whole run, like relics/
        # deck_template. potion_slots is the wiki-confirmed STS2 default (3);
        # Ascension-scaled slot counts aren't modeled. See potions.py.
        self.potions: List = []
        self.potion_slots = 3
        # Cards upgraded for THIS combat only (Armaments, Aggression). See
        # upgrade_for_combat() for why a bare card.upgrade() is wrong here.
        self.temp_upgrades: List = []
        # Cards given a temporary cost override, as (card, scope) with scope
        # "turn" or "combat". Same deck_template aliasing hazard as
        # temp_upgrades: a card in hand IS the deck object, so writing
        # `card.cost = 0` directly would make it free forever.
        self.temp_cost_cards: List = []
        self.temp_replay_cards: List = []
        self.next_attack_multiplier = 1
        self.extra_card_plays = 0     # Duplicator: next card played twice
        self.extra_turns = 0          # Ambergris
        self.retain_hand_turns = 0    # Stable Serum
        self.bonus_draw_turns = 0     # Clarity Extract
        self.bonus_energy_turns = 0   # Radiant Tincture
        self.chains_of_binding = 0    # Queen: first N cards drawn each turn are Bound
        self.bound_played_this_turn = 0
        self.cards_drawn_this_turn = 0
        # --- state read by the dynamic-cost system (Card.current_cost) ---
        # Kept as plain flags/counters rather than a list of callables: every
        # real STS2 effect in this class is one of these three shapes, and
        # flags are far easier to reset correctly at the right boundary.
        self.skills_cost_zero = False      # Corruption (whole combat)
        self.next_attack_free = False      # Unrelenting (until consumed)
        self.attacks_played_this_turn = 0  # Stomp reads this
        self.cards_played_this_turn = 0    # Ringing reads this
        self.skills_played_this_turn = 0   # Smoggy reads this
        # --- other card-driven state ---
        self.exhaust_skills = False        # Corruption's second half
        self.extra_attack_plays = 0        # One-Two Punch
        self.vulnerable_damage_bonus = 0.0        # Cruelty (combat)
        self.vulnerable_attacker_reduction = 0.0  # Colossus (this turn)
        # --- Colorless card state ---
        self.defend_block_bonus = 0        # Fasten
        self.no_card_block_turns = 0       # Panic Button
        self.draw_reduction = 0            # Mind Rot (while held)
        self.energy_reduction = 0          # Waste Away (while held)
        self.cards_played_this_combat = 0  # Gold Axe
        self.cards_drawn_this_combat = 0   # Automation
        self.gambit_armed = False          # The Gambit
        self.redirect_attacks_from = []    # Intercept: allies covered this turn
        self.share_block_with_allies = False   # Beacon of Hope
        self.nostalgia = False             # Nostalgia
        self.nostalgia_done_this_turn = False
        # Rebound: the card that armed it, or None. Was set ONLY in
        # start_combat(), so a Player that had not yet entered a fight did not
        # have the attribute at all -- which is why combat.py read it through
        # getattr. Declared here so the two reset paths agree.
        self.rebound_next_card = None
        self.panache_damage = 0            # Panache
        # Cards to put back in hand at the start of the next turn
        # (Thrumming Hatchet, Bolas).
        self.return_to_hand: List = []
        self.pending_end_of_turn_statuses: List = []
        # Deferred effects as [turns_remaining, when, fn]. `when` is "start"
        # or "end" of turn. One list rather than a field per card because
        # seven Colorless cards are all this shape (The Bomb, Relax,
        # Outmaneuver, Prolong, Toric Toughness, ...) and they only differ in
        # the delay and the payload.
        self.delayed_effects: List = []
        # Re-entrancy guards for cards that play other cards. Hellraiser can
        # chain (a drawn Pommel Strike draws more cards, which may be Strikes),
        # so depth is capped rather than trusted to terminate on its own.
        self._auto_play_depth = 0
        self._replaying_attack = False

    def upgrade_for_combat(self, card):
        """Upgrade a card for THIS FIGHT only, then undo it at combat end.

        `start_combat()` builds the draw pile with `list(self.deck_template)`
        -- a copy of the LIST, not of the Card objects -- so a card in hand
        is the very same object that lives in deck_template. Calling
        `card.upgrade()` on it therefore made the upgrade permanent for the
        whole run. That is a real pre-existing bug in Armaments (found while
        adding Aggression, which upgrades a card the same way): two
        Armaments plays across two fights would permanently upgrade the deck
        for free. Both now route through here."""
        if card.upgraded:
            return False
        card.upgrade()
        self.temp_upgrades.append(card)
        return True

    def revert_combat_upgrades(self):
        for card in self.temp_upgrades:
            card.upgraded = False
        self.temp_upgrades = []

    def set_temp_cost(self, card, cost: int, scope: str = "turn"):
        """Override a card's cost for this turn or this combat, reversibly.
        scope is "turn" or "combat"."""
        card.temp_cost = cost
        self.temp_cost_cards.append((card, scope))

    def clear_temp_costs(self, scope: str = "turn"):
        """Drop overrides of the given scope; "combat" drops everything,
        since a combat ending also ends the turn."""
        keep = []
        for card, s in self.temp_cost_cards:
            if scope == "combat" or s == scope:
                card.temp_cost = None
            else:
                keep.append((card, s))
        self.temp_cost_cards = keep

    def grant_replay(self, card, amount: int = 1):
        """Soldier's Stew: "gain 1 Replay this combat". Reverted at combat
        end for the same deck_template reason as temp upgrades/costs."""
        card.replay += amount
        self.temp_replay_cards.append(card)

    def clear_temp_replays(self):
        for card in self.temp_replay_cards:
            card.replay = 0
        self.temp_replay_cards = []

    def add_relic(self, relic):
        """Grant a relic: record it and fire its one-time on_pickup effect,
        if it has one (e.g. Strawberry's instant Max HP increase). Standing
        combat-start/combat-end effects fire every fight instead, from
        CombatEngine -- see relics.py."""
        self.relics.append(relic)
        if relic.on_pickup is not None:
            relic.on_pickup(self)

    def start_combat(self, seed: Optional[int] = None):
        if seed is not None:
            self.rng.seed(seed)
        for c in self.deck_template:
            c.combat_bonus_damage = 0
        self.draw_pile = list(self.deck_template)
        self.rng.shuffle(self.draw_pile)
        self.hand = []
        self.discard_pile = []
        self.exhaust_pile = []
        self.hp = self.max_hp
        self.block = 0
        self.statuses = {}
        self.alive = True
        self.exhausted_this_turn = []
        self.lost_hp_this_turn = 0
        self.lost_hp_this_combat = 0
        self.hp_loss_events_this_combat = 0
        self.retain_block = False
        self.no_more_draw_this_turn = False
        self.acted_this_turn = False
        self.hooks = {}
        self.armed_card_hooks = set()
        # Per-combat relic state -- NOT relic_counters, which is whole-run.
        self.pending_relic_block = 0
        self.pending_relic_draw = 0
        self.pending_relic_energy = 0
        self.flat_damage_reduction = 0
        self.next_attack_bonus_damage = 0
        self.next_attack_double = False
        self.card_damage_bonus = 0
        self.bonus_strength_below_half = 0
        self.retain_block_cap = 0
        self.conserve_energy = False
        self.skills_cost_zero = False
        self.next_attack_free = False
        self.attacks_played_this_turn = 0
        self.exhaust_skills = False
        self.extra_attack_plays = 0
        self.vulnerable_damage_bonus = 0.0
        self.vulnerable_attacker_reduction = 0.0
        self.defend_block_bonus = 0
        self.no_card_block_turns = 0
        self.draw_reduction = 0
        self.energy_reduction = 0
        self.cards_played_this_combat = 0
        self.cards_drawn_this_combat = 0
        self.gambit_armed = False
        self.redirect_attacks_from = []
        self.share_block_with_allies = False
        self.nostalgia = False
        self.nostalgia_done_this_turn = False
        self.panache_damage = 0
        self.rebound_next_card = None   # Rebound: the card that armed it
        self.return_to_hand = []
        self.delayed_effects = []
        self.pending_end_of_turn_statuses = []
        self._auto_play_depth = 0
        self._replaying_attack = False
        self.next_attack_multiplier = 1
        self.extra_card_plays = 0
        self.extra_turns = 0
        self.retain_hand_turns = 0
        self.bonus_draw_turns = 0
        self.bonus_energy_turns = 0
        self.chains_of_binding = 0
        self.bound_played_this_turn = 0
        self.cards_drawn_this_turn = 0
        self.clear_temp_costs("combat")
        self.clear_temp_replays()
        # Undo any combat-scoped upgrade left over from a previous fight
        # before this one starts, in case the combat ended in defeat and
        # never reached the normal revert.
        self.revert_combat_upgrades()

    # ---------- event hooks (Powers that trigger on other actions) ----------
    def register_hook(self, event: str, callback, expires_this_turn: bool = False):
        """Register a callback for an event this player cares about. Used by
        Powers like Dark Embrace ('whenever a card is Exhausted, draw') and
        turn-scoped ones like Rage ('whenever you play an Attack THIS TURN,
        gain Block'). callback(engine, player, **event_data) -> None."""
        self.hooks.setdefault(event, []).append((callback, expires_this_turn))

    def fire_hook(self, event: str, **event_data):
        if self.engine is None:
            return
        for callback, _ in list(self.hooks.get(event, [])):
            callback(self.engine, self, **event_data)

    def clear_turn_scoped_hooks(self):
        for event, entries in list(self.hooks.items()):
            self.hooks[event] = [(cb, exp) for cb, exp in entries if not exp]

    def lose_hp(self, amount: int, log=None, label: str = "hp loss") -> int:
        lost = super().lose_hp(amount, log=log, label=label)
        self.lost_hp_this_turn += lost
        self.lost_hp_this_combat += lost
        if lost:
            self.hp_loss_events_this_combat += 1
        return lost

    def add_to_hand(self, card, log: Optional[list] = None) -> bool:
        """Put a card into hand, honouring HAND_LIMIT. Returns True if it
        landed in hand, False if the hand was full and it went to the
        discard pile instead.

        Every "add a card to your Hand" effect goes through here -- there
        are 29 of them across cards/relics/potions/enemies, and before this
        existed each one appended directly, so Calamity, Hello World,
        Jackpot, Dual Wield and every enemy that shuffles a Status into your
        hand could all push it past 10."""
        if len(self.hand) >= HAND_LIMIT:
            self.discard_pile.append(card)
            if log is not None:
                log.append(f"{self.name}'s hand is full -- {card.name} goes to the discard pile")
            return False
        self.hand.append(card)   # the one place that may append directly
        return True

    def take_top_of_draw(self, log: Optional[list] = None):
        """Remove and return the top card of the draw pile, reshuffling the
        discard pile in if needed. None if both are empty.

        Distinct from draw_cards(1) on purpose: Havoc, Cascade and Mayhem
        play the top card of the draw pile WITHOUT it ever entering the
        hand, so the hand limit must not apply to them -- routing them
        through draw_cards made a full hand silently cancel the card. It
        also means they do not fire card_drawn or count toward "cards
        drawn", which is correct: they are not draws.
        """
        if not self.draw_pile:
            if not self.discard_pile:
                return None
            self.draw_pile = list(self.discard_pile)
            self.rng.shuffle(self.draw_pile)
            self.discard_pile = []
            if self.hooks.get("reshuffle"):
                self.fire_hook("reshuffle")
            if log is not None:
                log.append(f"{self.name} reshuffles discard into draw pile")
        return self.draw_pile.pop() if self.draw_pile else None

    def draw_cards(self, n: int, log: Optional[list] = None):
        if self.no_more_draw_this_turn:
            if log is not None:
                log.append(f"{self.name} cannot draw more cards this turn")
            return
        for _ in range(n):
            if not self.draw_pile:
                if not self.discard_pile:
                    break
                self.draw_pile = list(self.discard_pile)
                self.rng.shuffle(self.draw_pile)
                self.discard_pile = []
                # Stratagem: "Whenever you shuffle your Draw Pile, choose a
                # card from it to put into your Hand."
                if self.hooks.get("reshuffle"):
                    self.fire_hook("reshuffle")
                if log is not None:
                    log.append(f"{self.name} reshuffles discard into draw pile")
            if self.draw_pile:
                drawn = self.draw_pile.pop()
                # Hand limit. The card IS drawn -- it leaves the draw pile,
                # counts toward "cards drawn" and fires card_drawn -- it just
                # lands in the discard pile instead of the hand, which is
                # what the Mechanics page describes ("the remaining cards
                # entering the discard pile immediately"). Milling the rest
                # of a draw into the discard is therefore correct, not a bug:
                # holding a full hand through Retain has a real cost.
                if len(self.hand) >= HAND_LIMIT:
                    self.discard_pile.append(drawn)
                    if log is not None:
                        log.append(f"{self.name}'s hand is full -- {drawn.name} is discarded")
                else:
                    self.hand.append(drawn)
                # Per-card draw event (Hellraiser: "whenever you draw a card
                # containing 'Strike', it is played"). Guarded on `hooks` so
                # the common case -- nobody listening -- costs one dict lookup
                # on what is the hottest path in the engine.
                self.cards_drawn_this_turn += 1
                self.cards_drawn_this_combat += 1   # Automation
                # Chains of Binding: "the first X cards drawn each turn are
                # Afflicted with Bound." Bound is a per-CARD affliction, not
                # a status on the player, because only one Bound card may be
                # played per turn regardless of how many you hold.
                if self.cards_drawn_this_turn <= self.chains_of_binding:
                    drawn.bound = True
                # Void: "Whenever you draw this card, lose 1 Energy."
                if drawn.name == "Void":
                    self.energy = max(0, self.energy - 1)
                    if log is not None:
                        log.append(f"{self.name} loses 1 energy (Void)")
                if self.hooks.get("card_drawn"):
                    self.fire_hook("card_drawn", card=drawn)

    def start_turn(self, log: Optional[list] = None, base_draw: int = 5):
        # Ice Cream: "Energy is now conserved between turns."
        if self.conserve_energy:
            self.energy += self.max_energy
        else:
            self.energy = self.max_energy
        # Radiant Tincture: "+1 energy at the start of your next 3 turns".
        if self.bonus_energy_turns > 0:
            self.bonus_energy_turns -= 1
            self.energy += 1
        if self.bonus_draw_turns > 0:      # Clarity Extract
            self.bonus_draw_turns -= 1
            base_draw += 1
        # Waste Away: "Gain 1 less Energy per turn." Mind Rot: "Draw 1 fewer
        # card each turn." Both say EACH TURN, and a Status card spends most
        # of a fight outside the hand -- it is discarded at end of turn like
        # anything else. Counting only the hand made both penalties fire once
        # and then quietly stop. Recomputed from the whole deck every turn
        # rather than stored, so Exhausting the card (the real way out) does
        # end the penalty.
        def _copies(name):
            return sum(1 for pile in (self.hand, self.draw_pile, self.discard_pile)
                       for c in pile if c.name == name)
        self.energy_reduction = _copies("Waste Away")
        self.draw_reduction = _copies("Mind Rot")
        if self.energy_reduction:
            self.energy = max(0, self.energy - self.energy_reduction)
        base_draw = max(0, base_draw - self.draw_reduction)
        self.clear_temp_costs("turn")
        if not self.retain_block:
            # Sturdy Clamp: "up to 10 Block persists across turns."
            self.block = min(self.block, self.retain_block_cap)
        self.exhausted_this_turn = []
        self.lost_hp_this_turn = 0
        self.no_more_draw_this_turn = False
        self.acted_this_turn = False
        # Turn-scoped card state. next_attack_free is deliberately NOT reset:
        # Unrelenting says "the next Attack you play costs 0" with no turn
        # limit, so it survives until something actually consumes it.
        self.attacks_played_this_turn = 0
        self.cards_played_this_turn = 0    # Ringing reads this
        self.skills_played_this_turn = 0   # Smoggy reads this
        self.extra_attack_plays = 0
        self.vulnerable_attacker_reduction = 0.0
        self.nostalgia_done_this_turn = False
        # Rebound says "this turn", so an unspent charge expires here rather
        # than waiting for a card that may never come.
        self.rebound_next_card = None
        self.redirect_attacks_from = []
        if self.no_card_block_turns > 0:   # Panic Button
            self.no_card_block_turns -= 1
        # Thrumming Hatchet / Bolas: "at the start of your next turn, return
        # this to your Hand." Returned BEFORE the normal draw so the card is
        # held rather than competing with it.
        if self.return_to_hand:
            for c in self.return_to_hand:
                self.add_to_hand(c, log)
                if log is not None:
                    log.append(f"{c.name} returns to {self.name}'s hand")
            self.return_to_hand = []
        self.resolve_delayed_effects("start", log)
        self.tick_start_of_turn(log)
        # NOTE: the hand is discarded in end_turn(), not here. It used to be
        # discarded at the start of the turn, which quietly threw away any
        # card an ENEMY put into your hand during its own turn -- Myte's
        # "adds 2 Toxic to your Hand" was a no-op, and so was every future
        # effect of that shape. Discarding at end of turn matches the real
        # game's sequence (discard -> enemies act -> draw).
        self.draw_cards(base_draw, log)

    def add_delayed_effect(self, turns: int, when: str, fn):
        """Schedule `fn(player, log)` to run after `turns` more turn
        boundaries of the given kind. turns=1 means "next turn"."""
        self.delayed_effects.append([turns, when, fn])

    def resolve_delayed_effects(self, when: str, log: Optional[list] = None):
        """Tick every pending deferred effect, firing the ones that come due.

        Rebuilds the list rather than mutating in place because a firing
        effect is allowed to schedule another one (Rolling Boulder-style
        escalation), and appending to a list being iterated is how that
        turns into an infinite loop."""
        pending, self.delayed_effects = self.delayed_effects, []
        for entry in pending:
            turns, kind, fn = entry
            if kind != when:
                self.delayed_effects.append(entry)
                continue
            turns -= 1
            if turns > 0:
                self.delayed_effects.append([turns, kind, fn])
            else:
                fn(self, log)

    def end_turn(self, log: Optional[list] = None):
        self.apply_end_of_turn_gains(log)
        self.resolve_delayed_effects("end", log)
        self.decay_statuses_end_of_turn()
        # Doubt/Shame ("at the end of your turn, gain 1 Weak/Frail"). Queued
        # by CombatEngine._resolve_infection and applied HERE, after decay.
        # Applied before it, a 1-stack DURATION debuff is decremented back to
        # nothing in the same breath and the curse does literally nothing.
        for status, amount, source in self.pending_end_of_turn_statuses:
            self.add_status(status, amount)
            if log is not None:
                log.append(f"{self.name} gains {amount} {status.name.title()} ({source})")
        self.pending_end_of_turn_statuses = []
        self.clear_turn_scoped_hooks()
        # Hand disposal. Each card is exhausted, kept, or discarded, and
        # four separate effects feed into that one decision:
        #   Ethereal, per card (Apparition, Void, Dazed, four curses)
        #   Ethereal, hand-wide (Hex)
        #   Retain, per card (Purity, Restlessness, Poor Sleep, ...)
        #   Retain, hand-wide (Stable Serum, Equilibrium, Salvo)
        # Ethereal outranks Retain: a retained hand still loses its Ethereal
        # cards, which is exactly what makes Apparition and Void clear
        # themselves instead of jamming the hand forever.
        #
        # A retained hand no longer grows without bound: HAND_LIMIT is
        # enforced in draw_cards and add_to_hand, so next turn's draw simply
        # overflows into the discard pile once the hand is full.
        retain_all = self.retain_hand_turns > 0
        if retain_all:
            self.retain_hand_turns -= 1
            if log is not None:
                log.append(f"{self.name} retains their hand")
        hex_active = self.get_status(StatusType.HEX) > 0
        if hex_active and self.hand and log is not None:
            log.append(f"{self.name}'s hand is Ethereal and exhausts (Hex)")
        # Routed through the engine so exhaust counters and card_exhausted
        # listeners stay correct.
        engine = self.engine
        kept, discarded = [], []
        for c in list(self.hand):
            if hex_active or c.is_ethereal():
                if engine is not None:
                    engine.exhaust_card(self, c)
                else:
                    self.exhaust_pile.append(c)
            elif retain_all or c.retains_now():
                kept.append(c)
            else:
                discarded.append(c)
        self.discard_pile.extend(discarded)
        self.hand = kept
