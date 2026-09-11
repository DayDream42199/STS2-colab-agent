"""Entity model: shared base for Player and Enemy, handling HP, block, statuses, and damage..."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import random

from .statuses import (
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


HAND_LIMIT = 10


CONTENT_RNG = random.Random()


def seed_content(seed: Optional[int] = None):
    """Reseed the construction-time rng."""
    CONTENT_RNG.seed(seed)


@dataclass
class DamageResult:
    raw: int
    to_block: int
    to_hp: int
    killed: bool


class Entity:

    no_card_block_turns = 0
    next_attack_bonus_damage = 0
    next_attack_double = False
    next_attack_multiplier = 1
    card_damage_bonus = 0
    bonus_strength_below_half = 0
    flat_damage_reduction = 0
    vulnerable_damage_bonus = 0.0
    vulnerable_attacker_reduction = 0.0
    redirect_attacks_from = ()
    engine = None

    attacked_by_this_turn = None
    knockdown = None
    invulnerable = False
    painful_stabs = 0
    hit_by_current_card = False
    stunned_turns = 0

    def __init__(self, name: str, max_hp: int):
        self.name = name
        self.max_hp = max_hp
        self.hp = max_hp
        self.block = 0
        self.statuses: Dict[StatusType, int] = {}
        self.alive = True

    def add_status(self, status: StatusType, amount: int = 1, applier: "Entity" = None):
        """applier is who is APPLYING the status, and exists for powers that read "whenever YOU apply X"..."""
        if amount == 0:
            return
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
        """Apply each status's real turn-boundary behavior (see statuses.py) instead of one flat decay rule."""
        for s in list(self.statuses.keys()):
            _, behavior = STATUS_META.get(s, (StackType.INTENSITY, TurnBehavior.PERMANENT))
            if behavior == TurnBehavior.DECREMENTED:
                self.add_status(s, -1)
            elif behavior == TurnBehavior.REMOVED:
                self.statuses.pop(s, None)

    def tick_start_of_turn(self, log: Optional[list] = None):
        """Start-of-turn statuses."""
        if self.get_status(StatusType.POISON) > 0:
            n = self.get_status(StatusType.POISON)
            self.take_damage(n, source_is_attack=False, log=log, label="poison")
            self.add_status(StatusType.POISON, -1)

    def apply_end_of_turn_gains(self, log: Optional[list] = None):
        """Everything the powers module defines as happening at end of turn: Metallicize/Plating block..."""
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

    def gain_block(self, amount: int, from_card: bool = True):
        """`from_card` distinguishes Block granted BY A CARD from Block granted by a relic, potion or..."""
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
        """Block from a relic, potion or power."""
        return self.gain_block(amount, from_card=False)

    def clear_block(self):
        self.block = 0

    def deal_attack_damage(self, base_amount: int) -> int:
        """Compute outgoing damage from THIS entity as attacker, applying strength and weak."""
        amount = base_amount + net_strength(self.statuses)
        vigor = self.get_status(StatusType.VIGOR)
        if vigor:
            amount += vigor
            self.statuses.pop(StatusType.VIGOR, None)
        amount += self.next_attack_bonus_damage
        amount += self.card_damage_bonus
        below_half = self.bonus_strength_below_half
        if below_half and self.hp * 2 <= self.max_hp:
            amount += below_half
        amount = amount * damage_multiplier_for_attacker(self.statuses)
        if self.next_attack_double:
            amount *= 2
        mult = self.next_attack_multiplier
        if mult != 1:
            amount *= mult
            self.next_attack_multiplier = 1
        if self.next_attack_bonus_damage:
            self.next_attack_bonus_damage = 0
        if self.next_attack_double:
            self.next_attack_double = False
        return max(0, round(amount))

    def take_damage(self, raw_amount: int, source_is_attack: bool = True,
                     log: Optional[list] = None, label: str = "attack",
                     attacker: Optional["Entity"] = None) -> DamageResult:
        """attacker is who is swinging, and exists solely so Thorns can hit back."""
        amount = raw_amount
        if source_is_attack and attacker is not None:
            seen = self.attacked_by_this_turn
            if seen is not None:
                seen.append(attacker)
            kd = self.knockdown
            if kd is not None and attacker is not kd[0]:
                amount *= kd[1]
        if source_is_attack:
            vuln_bonus = attacker.vulnerable_damage_bonus if attacker else 0.0
            amount = amount * damage_multiplier_for_defender(self.statuses, vuln_bonus)
            if attacker is not None and attacker.get_status(StatusType.VULNERABLE) > 0:
                amount *= 1.0 - self.vulnerable_attacker_reduction
        amount = max(0, round(amount))
        reduction = self.flat_damage_reduction
        if reduction and amount > 0:
            amount = max(0, amount - reduction)
        if source_is_attack and self.get_status(StatusType.SOAR) > 0:
            amount = amount * 0.5
        if source_is_attack and self.get_status(StatusType.FLUTTER) > 0:
            amount = amount * 0.5
            self.add_status(StatusType.FLUTTER, -1)
            if self.get_status(StatusType.FLUTTER) <= 0:
                self.stunned_turns = max(self.stunned_turns, 1)
                if log is not None:
                    log.append(f"{self.name} is stunned (Flutter broken)")
        amount = max(0, round(amount))
        if amount > 0 and self.get_status(StatusType.INTANGIBLE) > 0:
            amount = 1
        if self.invulnerable:
            amount = 0

        if source_is_attack and amount > 0:
            self.hit_by_current_card = True

        absorbed = min(self.block, amount)
        self.block -= absorbed
        remainder = amount - absorbed
        if remainder > 0 and self.get_status(StatusType.BUFFER) > 0:
            self.add_status(StatusType.BUFFER, -1)
            if log is not None:
                log.append(f"{self.name} prevents the HP loss (Buffer)")
            remainder = 0
        if remainder > 0 and self.get_status(StatusType.SLIPPERY) > 0:
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
        hive = self.get_status(StatusType.PERSONAL_HIVE)
        if hive and source_is_attack and amount > 0 and attacker is not None \
                and hasattr(attacker, "draw_pile"):
            from .cards import make_dazed
            for _ in range(hive):
                attacker.draw_pile.insert(0, make_dazed())
            if log is not None:
                log.append(f"{attacker.name} gains {hive} Dazed (Personal Hive)")
        if attacker is not None and source_is_attack and remainder > 0:
            suck = attacker.get_status(StatusType.SUCK)
            if suck:
                attacker.add_status(StatusType.STRENGTH, suck)
                if log is not None:
                    log.append(f"{attacker.name} gains {suck} Strength (Suck)")
        stabs = self.painful_stabs
        if stabs and remainder > 0 and attacker is not None and hasattr(attacker, "discard_pile"):
            from .cards import make_wound
            for _ in range(stabs):
                attacker.discard_pile.append(make_wound())
            if log is not None:
                log.append(f"{attacker.name} gains {stabs} Wound (Painful Stabs)")
        self._retaliate_thorns(amount, source_is_attack, attacker, log)
        return DamageResult(raw=raw_amount, to_block=absorbed, to_hp=remainder, killed=killed)

    def _retaliate_thorns(self, amount: int, source_is_attack: bool,
                           attacker: Optional["Entity"], log: Optional[list] = None):
        """Thorns: "When hit by an attack, deal X damage back."""
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
        """Direct HP loss that ignores Block entirely -- matches real STS2 card wording like 'Lose 2 HP'..."""
        amount = max(0, amount)
        reduction = self.flat_damage_reduction
        if reduction and amount > 0:
            amount = max(0, amount - reduction)
        if amount > 0 and self.get_status(StatusType.INTANGIBLE) > 0:
            amount = 1
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
        self.deck_template = list(deck)
        self.draw_pile = []
        self.hand = []
        self.discard_pile = []
        self.exhaust_pile = []
        self.rng = random.Random(CONTENT_RNG.getrandbits(64))
        self.exhausted_this_turn = []
        self.lost_hp_this_turn = 0
        self.no_more_draw_this_turn = False
        self.lost_hp_this_combat = 0
        self.hp_loss_events_this_combat = 0
        self.retain_block = False
        self.armed_card_hooks = set()
        self.acted_this_turn = False
        self.engine = None
        self.hooks: Dict[str, List] = {}
        self.relics: List = []
        self.relic_counters: Dict[str, int] = {}
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
        self.potions: List = []
        self.potion_slots = 3
        self.temp_upgrades: List = []
        self.temp_cost_cards: List = []
        self.temp_replay_cards: List = []
        self.next_attack_multiplier = 1
        self.extra_card_plays = 0
        self.extra_turns = 0
        self.retain_hand_turns = 0
        self.bonus_draw_turns = 0
        self.bonus_energy_turns = 0
        self.chains_of_binding = 0
        self.bound_played_this_turn = 0
        self.cards_drawn_this_turn = 0
        self.skills_cost_zero = False
        self.next_attack_free = False
        self.attacks_played_this_turn = 0
        self.cards_played_this_turn = 0
        self.skills_played_this_turn = 0
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
        self.rebound_next_card = None
        self.panache_damage = 0
        self.return_to_hand: List = []
        self.pending_end_of_turn_statuses: List = []
        self.delayed_effects: List = []
        self._auto_play_depth = 0
        self._replaying_attack = False

    def upgrade_for_combat(self, card):
        """Upgrade a card for THIS FIGHT only, then undo it at combat end."""
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
        """Override a card's cost for this turn or this combat, reversibly. scope is "turn" or "combat"."""
        card.temp_cost = cost
        self.temp_cost_cards.append((card, scope))

    def clear_temp_costs(self, scope: str = "turn"):
        """Drop overrides of the given scope; "combat" drops everything, since a combat ending also ends..."""
        keep = []
        for card, s in self.temp_cost_cards:
            if scope == "combat" or s == scope:
                card.temp_cost = None
            else:
                keep.append((card, s))
        self.temp_cost_cards = keep

    def grant_replay(self, card, amount: int = 1):
        """Soldier's Stew: "gain 1 Replay this combat"."""
        card.replay += amount
        self.temp_replay_cards.append(card)

    def clear_temp_replays(self):
        for card in self.temp_replay_cards:
            card.replay = 0
        self.temp_replay_cards = []

    def add_relic(self, relic):
        """Grant a relic: record it and fire its one-time on_pickup effect, if it has one (e.g."""
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
        self.rebound_next_card = None
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
        self.revert_combat_upgrades()

    def register_hook(self, event: str, callback, expires_this_turn: bool = False):
        """Register a callback for an event this player cares about."""
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
        """Put a card into hand, honouring HAND_LIMIT."""
        if len(self.hand) >= HAND_LIMIT:
            self.discard_pile.append(card)
            if log is not None:
                log.append(f"{self.name}'s hand is full -- {card.name} goes to the discard pile")
            return False
        self.hand.append(card)
        return True

    def take_top_of_draw(self, log: Optional[list] = None):
        """Remove and return the top card of the draw pile, reshuffling the discard pile in if needed."""
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
                if self.hooks.get("reshuffle"):
                    self.fire_hook("reshuffle")
                if log is not None:
                    log.append(f"{self.name} reshuffles discard into draw pile")
            if self.draw_pile:
                drawn = self.draw_pile.pop()
                if len(self.hand) >= HAND_LIMIT:
                    self.discard_pile.append(drawn)
                    if log is not None:
                        log.append(f"{self.name}'s hand is full -- {drawn.name} is discarded")
                else:
                    self.hand.append(drawn)
                self.cards_drawn_this_turn += 1
                self.cards_drawn_this_combat += 1
                if self.cards_drawn_this_turn <= self.chains_of_binding:
                    drawn.bound = True
                if drawn.name == "Void":
                    self.energy = max(0, self.energy - 1)
                    if log is not None:
                        log.append(f"{self.name} loses 1 energy (Void)")
                if self.hooks.get("card_drawn"):
                    self.fire_hook("card_drawn", card=drawn)

    def start_turn(self, log: Optional[list] = None, base_draw: int = 5):
        if self.conserve_energy:
            self.energy += self.max_energy
        else:
            self.energy = self.max_energy
        if self.bonus_energy_turns > 0:
            self.bonus_energy_turns -= 1
            self.energy += 1
        if self.bonus_draw_turns > 0:
            self.bonus_draw_turns -= 1
            base_draw += 1
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
            self.block = min(self.block, self.retain_block_cap)
        self.exhausted_this_turn = []
        self.lost_hp_this_turn = 0
        self.no_more_draw_this_turn = False
        self.acted_this_turn = False
        self.attacks_played_this_turn = 0
        self.cards_played_this_turn = 0
        self.skills_played_this_turn = 0
        self.extra_attack_plays = 0
        self.vulnerable_attacker_reduction = 0.0
        self.nostalgia_done_this_turn = False
        self.rebound_next_card = None
        self.redirect_attacks_from = []
        if self.no_card_block_turns > 0:
            self.no_card_block_turns -= 1
        if self.return_to_hand:
            for c in self.return_to_hand:
                self.add_to_hand(c, log)
                if log is not None:
                    log.append(f"{c.name} returns to {self.name}'s hand")
            self.return_to_hand = []
        self.resolve_delayed_effects("start", log)
        self.tick_start_of_turn(log)
        self.draw_cards(base_draw, log)

    def add_delayed_effect(self, turns: int, when: str, fn):
        """Schedule `fn(player, log)` to run after `turns` more turn boundaries of the given kind. turns=1..."""
        self.delayed_effects.append([turns, when, fn])

    def resolve_delayed_effects(self, when: str, log: Optional[list] = None):
        """Tick every pending deferred effect, firing the ones that come due."""
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
        for status, amount, source in self.pending_end_of_turn_statuses:
            self.add_status(status, amount)
            if log is not None:
                log.append(f"{self.name} gains {amount} {status.name.title()} ({source})")
        self.pending_end_of_turn_statuses = []
        self.clear_turn_scoped_hooks()
        retain_all = self.retain_hand_turns > 0
        if retain_all:
            self.retain_hand_turns -= 1
            if log is not None:
                log.append(f"{self.name} retains their hand")
        hex_active = self.get_status(StatusType.HEX) > 0
        if hex_active and self.hand and log is not None:
            log.append(f"{self.name}'s hand is Ethereal and exhausts (Hex)")
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
