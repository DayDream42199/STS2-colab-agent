"""Relic model + a real Ironclad-relevant relic pool, sourced from the wiki the same way..."""

from dataclasses import dataclass
from typing import Callable, Optional

from .statuses import StatusType, DEBUFF_STATUSES
from .cards import CardType, CARD_POOL_IRONCLAD
from .potions import POTION_SHAPED_ROCK


@dataclass
class Relic:
    name: str
    rarity: str
    description: str
    on_pickup: Optional[Callable] = None
    on_turn_start: Optional[Callable] = None
    on_turn_end: Optional[Callable] = None
    on_combat_end: Optional[Callable] = None
    on_card_added: Optional[Callable] = None


def _register_once_per_combat(player, event, effect):
    """`effect(engine, player, **kwargs)` fires the first time `event` fires this combat, then goes..."""
    fired = {"done": False}

    def _cb(engine, player, **kwargs):
        if fired["done"]:
            return
        fired["done"] = True
        effect(engine, player, **kwargs)

    player.register_hook(event, _cb)


def _register_every_n_per_turn(player, event, n, effect):
    """`effect(engine, player)` fires every Nth time `event` fires WITHIN THE CURRENT TURN, resetting..."""
    state = {"count": 0, "turn": 0}

    def _cb(engine, player, **kwargs):
        if engine.turn_number != state["turn"]:
            state["turn"] = engine.turn_number
            state["count"] = 0
        state["count"] += 1
        if state["count"] >= n:
            state["count"] = 0
            effect(engine, player)

    player.register_hook(event, _cb)


def _register_every_n_per_combat(player, event, n, effect):
    """Same as above but counts across the WHOLE combat, no per-turn reset -- matches "every time you..."""
    state = {"count": 0}

    def _cb(engine, player, **kwargs):
        state["count"] += 1
        if state["count"] >= n:
            state["count"] = 0
            effect(engine, player)

    player.register_hook(event, _cb)


def _burning_blood_end(engine, player):
    before = player.hp
    player.heal(6)
    engine.log.append(f"{player.name} heals {player.hp - before} HP (Burning Blood)")


BURNING_BLOOD = Relic(
    "Burning Blood", "Starter",
    "At the end of combat, heal 6 HP.",
    on_combat_end=_burning_blood_end,
)


def _blood_vial_start(engine, player, turn_number):
    if turn_number != 1:
        return
    before = player.hp
    player.heal(2)
    engine.log.append(f"{player.name} heals {player.hp - before} HP (Blood Vial)")


def _anchor_start(engine, player, turn_number):
    if turn_number != 1:
        return
    gained = player.gain_block_noncard(10)
    engine.log.append(f"{player.name} gains {gained} block (Anchor)")


def _vajra_start(engine, player, turn_number):
    if turn_number != 1:
        return
    player.add_status(StatusType.STRENGTH, 1)
    engine.log.append(f"{player.name} gains 1 Strength (Vajra)")


def _bag_of_marbles_start(engine, player, turn_number):
    if turn_number != 1:
        return
    for e in engine.enemies:
        if e.alive:
            e.add_status(StatusType.VULNERABLE, 1, applier=player)
    engine.log.append("ALL enemies gain 1 Vulnerable (Bag of Marbles)")


def _bag_of_preparation_start(engine, player, turn_number):
    if turn_number != 1:
        return
    engine.draw_extra(player, 2)
    engine.log.append(f"{player.name} draws 2 additional cards (Bag of Preparation)")


def _centennial_puzzle_start(engine, player, turn_number):
    if turn_number != 1:
        return

    def _effect(engine, player, **kwargs):
        engine.draw_extra(player, 3)
        engine.log.append(f"{player.name} draws 3 cards (Centennial Puzzle)")

    _register_once_per_combat(player, "hp_lost", _effect)


def _strawberry_pickup(player):
    player.max_hp += 7
    player.hp += 7


def _festive_popper_start(engine, player, turn_number):
    if turn_number != 1:
        return
    for e in engine.enemies:
        if e.alive:
            dmg = player.deal_attack_damage(9)
            e.take_damage(dmg, log=engine.log, label="Festive Popper", attacker=player)


def _bronze_scales_start(engine, player, turn_number):
    if turn_number != 1:
        return
    player.add_status(StatusType.THORNS, 3)
    engine.log.append(f"{player.name} gains 3 Thorns (Bronze Scales)")


def _gorget_start(engine, player, turn_number):
    if turn_number != 1:
        return
    player.add_status(StatusType.PLATED_ARMOR, 4)
    engine.log.append(f"{player.name} gains 4 Plating (Gorget)")


def _happy_flower_start(engine, player, turn_number):
    if turn_number % 3 != 0:
        return
    player.energy += 1
    engine.log.append(f"{player.name} gains 1 Energy (Happy Flower)")


def _lantern_start(engine, player, turn_number):
    if turn_number != 1:
        return
    player.energy += 1
    engine.log.append(f"{player.name} gains 1 Energy (Lantern)")


def _oddly_smooth_stone_start(engine, player, turn_number):
    if turn_number != 1:
        return
    player.add_status(StatusType.DEXTERITY, 1)
    engine.log.append(f"{player.name} gains 1 Dexterity (Oddly Smooth Stone)")


def _pendulum_start(engine, player, turn_number):
    if turn_number % 3 != 0:
        return
    engine.draw_extra(player, 1)
    engine.log.append(f"{player.name} draws 1 card (Pendulum)")


def _red_mask_start(engine, player, turn_number):
    if turn_number != 1:
        return
    for e in engine.enemies:
        if e.alive:
            e.add_status(StatusType.WEAK, 1)
    engine.log.append("ALL enemies gain 1 Weak (Red Mask)")


def _war_paint_pickup(player):
    skills = [c for c in player.deck_template if c.card_type == CardType.SKILL and not c.upgraded]
    for c in player.rng.sample(skills, k=min(2, len(skills))):
        c.upgrade()


def _whetstone_pickup(player):
    attacks = [c for c in player.deck_template if c.card_type == CardType.ATTACK and not c.upgraded]
    for c in player.rng.sample(attacks, k=min(2, len(attacks))):
        c.upgrade()


def _akabeko_start(engine, player, turn_number):
    if turn_number != 1:
        return
    player.next_attack_bonus_damage += 8
    engine.log.append(f"{player.name} gains 8 Vigor (Akabeko)")


def _candelabra_start(engine, player, turn_number):
    if turn_number != 2:
        return
    player.energy += 2
    engine.log.append(f"{player.name} gains 2 Energy (Candelabra)")


def _gremlin_horn_start(engine, player, turn_number):
    if turn_number != 1:
        return

    def _effect(engine, player, **kwargs):
        player.energy += 1
        engine.draw_extra(player, 1)
        engine.log.append(f"{player.name} gains 1 Energy and draws 1 card (Gremlin Horn)")

    player.register_hook("enemy_died", _effect)


def _horn_cleat_start(engine, player, turn_number):
    if turn_number != 2:
        return
    gained = player.gain_block_noncard(14)
    engine.log.append(f"{player.name} gains {gained} block (Horn Cleat)")


def _joss_paper_start(engine, player, turn_number):
    if turn_number != 1:
        return

    def _effect(engine, player):
        engine.draw_extra(player, 1)
        engine.log.append(f"{player.name} draws 1 card (Joss Paper)")

    _register_every_n_per_combat(player, "card_exhausted", 5, _effect)


def _kusarigama_start(engine, player, turn_number):
    if turn_number != 1:
        return

    def _effect(engine, player):
        target = engine.random_alive_enemy(player)
        if target is not None:
            target.take_damage(6, source_is_attack=False, log=engine.log, label="Kusarigama")

    _register_every_n_per_turn(player, "attack_played", 3, _effect)


def _letter_opener_start(engine, player, turn_number):
    if turn_number != 1:
        return

    def _effect(engine, player):
        for e in engine.enemies:
            if e.alive:
                e.take_damage(5, source_is_attack=False, log=engine.log, label="Letter Opener")

    _register_every_n_per_turn(player, "skill_played", 3, _effect)


def _mercury_hourglass_start(engine, player, turn_number):
    for e in engine.enemies:
        if e.alive:
            e.take_damage(3, source_is_attack=False, log=engine.log, label="Mercury Hourglass")


def _nunchaku_start(engine, player, turn_number):
    if turn_number != 1:
        return

    def _effect(engine, player):
        player.energy += 1
        engine.log.append(f"{player.name} gains 1 Energy (Nunchaku)")

    _register_every_n_per_combat(player, "attack_played", 10, _effect)


def _orichalcum_end(engine, player):
    if player.block <= 0:
        gained = player.gain_block_noncard(6)
        engine.log.append(f"{player.name} gains {gained} block (Orichalcum)")


def _ornamental_fan_start(engine, player, turn_number):
    if turn_number != 1:
        return

    def _effect(engine, player):
        gained = player.gain_block_noncard(4)
        engine.log.append(f"{player.name} gains {gained} block (Ornamental Fan)")

    _register_every_n_per_turn(player, "attack_played", 3, _effect)


def _parrying_shield_end(engine, player):
    if player.block >= 10:
        target = engine.random_alive_enemy(player)
        if target is not None:
            target.take_damage(6, source_is_attack=False, log=engine.log, label="Parrying Shield")


def _pear_pickup(player):
    player.max_hp += 10
    player.hp += 10


def _pen_nib_start(engine, player, turn_number):
    if turn_number != 1:
        return

    def _effect(engine, player):
        player.next_attack_double = True
        engine.log.append(f"{player.name}'s next Attack will deal double damage (Pen Nib)")

    _register_every_n_per_combat(player, "attack_played", 10, _effect)


def _permafrost_start(engine, player, turn_number):
    if turn_number != 1:
        return

    def _effect(engine, player, **kwargs):
        gained = player.gain_block_noncard(7)
        engine.log.append(f"{player.name} gains {gained} block (Permafrost)")

    _register_once_per_combat(player, "power_played", _effect)


def _ripple_basin_start(engine, player, turn_number):
    if turn_number != 1:
        return
    player.relic_counters["_attacked_this_turn"] = 0

    def _mark_attacked(engine, player, **kwargs):
        player.relic_counters["_attacked_this_turn"] = engine.turn_number

    player.register_hook("attack_played", _mark_attacked)


def _ripple_basin_end(engine, player):
    if player.relic_counters.get("_attacked_this_turn") != engine.turn_number:
        gained = player.gain_block_noncard(4)
        engine.log.append(f"{player.name} gains {gained} block (Ripple Basin)")


def _sparkling_rouge_start(engine, player, turn_number):
    if turn_number != 3:
        return
    player.add_status(StatusType.STRENGTH, 1)
    player.add_status(StatusType.DEXTERITY, 1)
    engine.log.append(f"{player.name} gains 1 Strength and 1 Dexterity (Sparkling Rouge)")


def _stone_cracker_start(engine, player, turn_number):
    if turn_number != 1:
        return
    pool = list(player.draw_pile)
    for c in player.rng.sample(pool, k=min(2, len(pool))):
        c.upgrade()
    engine.log.append(f"{player.name} upgrades 2 cards in the Draw Pile (Stone Cracker)")


def _tuning_fork_start(engine, player, turn_number):
    if turn_number != 1:
        return

    def _effect(engine, player):
        gained = player.gain_block_noncard(7)
        engine.log.append(f"{player.name} gains {gained} block (Tuning Fork)")

    _register_every_n_per_combat(player, "skill_played", 10, _effect)


def _vambrace_start(engine, player, turn_number):
    if turn_number != 1:
        return

    def _effect(engine, player, **kwargs):
        amount = kwargs.get("amount", 0)
        if amount:
            player.block += amount
            engine.log.append(f"{player.name} gains {amount} additional block (Vambrace)")

    _register_once_per_combat(player, "block_gained", _effect)


def _self_forming_clay_start(engine, player, turn_number):
    if turn_number != 1:
        return

    def _on_hp_lost(engine, player, **kwargs):
        player.pending_relic_block += 3

    player.register_hook("hp_lost", _on_hp_lost)


def _twisted_funnel_start(engine, player, turn_number):
    if turn_number != 1:
        return
    for e in engine.enemies:
        if e.alive:
            e.add_status(StatusType.POISON, 4)
    engine.log.append("ALL enemies gain 4 Poison (Twisted Funnel)")


def _art_of_war_start(engine, player, turn_number):
    if turn_number != 1:
        return
    player.relic_counters["_attacked_this_turn_aow"] = 0

    def _mark_attacked(engine, player, **kwargs):
        player.relic_counters["_attacked_this_turn_aow"] = engine.turn_number

    player.register_hook("attack_played", _mark_attacked)


def _art_of_war_end(engine, player):
    if player.relic_counters.get("_attacked_this_turn_aow") != engine.turn_number:
        player.pending_relic_energy += 1


def _beating_remnant_start(engine, player, turn_number):
    """player.lost_hp_this_turn only tracks lose_hp()-sourced losses (self- inflicted card costs like..."""
    if turn_number == 1:
        def _track(engine, player, **kwargs):
            player.relic_counters["_hp_lost_this_turn_br"] = \
                player.relic_counters.get("_hp_lost_this_turn_br", 0) + kwargs.get("amount", 0)
        player.register_hook("hp_lost", _track)


def _beating_remnant_end(engine, player):
    lost = player.relic_counters.get("_hp_lost_this_turn_br", 0)
    if lost > 20:
        excess = lost - 20
        player.heal(excess)
        engine.log.append(f"{player.name} heals {excess} HP -- can't lose more than 20 HP/turn (Beating Remnant)")
    player.relic_counters["_hp_lost_this_turn_br"] = 0


def _bellows_start(engine, player, turn_number):
    if turn_number != 1:
        return
    for c in player.hand:
        c.upgrade()
    engine.log.append(f"{player.name}'s hand is Upgraded (Bellows)")


def _captains_wheel_start(engine, player, turn_number):
    if turn_number != 3:
        return
    gained = player.gain_block_noncard(18)
    engine.log.append(f"{player.name} gains {gained} block (Captain's Wheel)")


def _chandelier_start(engine, player, turn_number):
    if turn_number != 3:
        return
    player.energy += 3
    engine.log.append(f"{player.name} gains 3 Energy (Chandelier)")


def _cloak_clasp_end(engine, player):
    gained = player.gain_block_noncard(len(player.hand))
    if gained:
        engine.log.append(f"{player.name} gains {gained} block, 1 per card in Hand (Cloak Clasp)")


def _frozen_egg_added(player, card):
    if card.card_type == CardType.POWER and not card.upgraded:
        card.upgrade()


def _game_piece_start(engine, player, turn_number):
    if turn_number != 1:
        return

    def _effect(engine, player, **kwargs):
        engine.draw_extra(player, 1)
        engine.log.append(f"{player.name} draws 1 card (Game Piece)")

    player.register_hook("power_played", _effect)


def _intimidating_helmet_start(engine, player, turn_number):
    if turn_number != 1:
        return

    def _effect(engine, player, **kwargs):
        card = kwargs.get("card")
        cost = card.current_cost(player) if card is not None else 0
        if cost == "X" or (isinstance(cost, int) and cost >= 2):
            gained = player.gain_block_noncard(4)
            engine.log.append(f"{player.name} gains {gained} block (Intimidating Helmet)")

    player.register_hook("card_played", _effect)


def _kunai_start(engine, player, turn_number):
    if turn_number != 1:
        return

    def _effect(engine, player):
        player.add_status(StatusType.DEXTERITY, 1)
        engine.log.append(f"{player.name} gains 1 Dexterity (Kunai)")

    _register_every_n_per_turn(player, "attack_played", 3, _effect)


def _lizard_tail_start(engine, player, turn_number):
    if turn_number != 1 or player.relic_counters.get("Lizard Tail used"):
        return

    def _on_hp_lost(engine, player, **kwargs):
        if player.hp <= 0 and not player.relic_counters.get("Lizard Tail used"):
            player.relic_counters["Lizard Tail used"] = 1
            player.hp = player.max_hp // 2
            player.alive = True
            engine.log.append(f"{player.name} would have died, but Lizard Tail heals to {player.hp} HP!")

    player.register_hook("hp_lost", _on_hp_lost)


def _mango_pickup(player):
    player.max_hp += 14
    player.hp += 14


def _meat_on_the_bone_end(engine, player):
    if player.hp <= player.max_hp / 2:
        before = player.hp
        player.heal(12)
        engine.log.append(f"{player.name} heals {player.hp - before} HP (Meat on the Bone)")


def _molten_egg_added(player, card):
    if card.card_type == CardType.ATTACK and not card.upgraded:
        card.upgrade()


def _pocketwatch_start(engine, player, turn_number):
    player.relic_counters["_cards_played_this_turn_pw"] = 0
    if turn_number != 1:
        return

    def _count(engine, player, **kwargs):
        player.relic_counters["_cards_played_this_turn_pw"] = \
            player.relic_counters.get("_cards_played_this_turn_pw", 0) + 1

    player.register_hook("card_played", _count)


def _pocketwatch_end(engine, player):
    if player.relic_counters.get("_cards_played_this_turn_pw", 0) <= 3:
        player.pending_relic_draw += 3
    player.relic_counters["_cards_played_this_turn_pw"] = 0


def _rainbow_ring_start(engine, player, turn_number):
    if turn_number != 1:
        return
    seen = {"attack": None, "skill": None, "power": None}

    def _maybe_fire(kind):
        if seen[kind] == engine.turn_number:
            return
        seen[kind] = engine.turn_number
        if all(v == engine.turn_number for v in seen.values()):
            player.add_status(StatusType.STRENGTH, 1)
            player.add_status(StatusType.DEXTERITY, 1)
            engine.log.append(f"{player.name} gains 1 Strength and 1 Dexterity (Rainbow Ring)")

    player.register_hook("attack_played", lambda engine, player, **kw: _maybe_fire("attack"))
    player.register_hook("skill_played", lambda engine, player, **kw: _maybe_fire("skill"))
    player.register_hook("power_played", lambda engine, player, **kw: _maybe_fire("power"))


def _stone_calendar_end(engine, player):
    if engine.turn_number == 7:
        for e in engine.enemies:
            if e.alive:
                e.take_damage(52, source_is_attack=False, log=engine.log, label="Stone Calendar")


def _toxic_egg_added(player, card):
    if card.card_type == CardType.SKILL and not card.upgraded:
        card.upgrade()


def _tungsten_rod_start(engine, player, turn_number):
    if turn_number != 1:
        return
    player.flat_damage_reduction += 1


def _unceasing_top_start(engine, player, turn_number):
    if turn_number != 1:
        return

    def _effect(engine, player, **kwargs):
        if not player.hand:
            engine.draw_extra(player, 1)
            engine.log.append(f"{player.name} draws 1 card (Unceasing Top)")

    player.register_hook("card_played", _effect)


def _vexing_puzzlebox_start(engine, player, turn_number):
    if turn_number != 1:
        return
    factory = player.rng.choice(CARD_POOL_IRONCLAD)
    card = factory()
    card.cost = 0
    player.add_to_hand(card)
    engine.log.append(f"{player.name} adds {card.name} (free this turn) to their Hand (Vexing Puzzlebox)")


def _charons_ashes_start(engine, player, turn_number):
    if turn_number != 1:
        return

    def _effect(engine, player, **kwargs):
        for e in engine.enemies:
            if e.alive:
                e.take_damage(3, source_is_attack=False, log=engine.log, label="Charon's Ashes")

    player.register_hook("card_exhausted", _effect)


def _demon_tongue_start(engine, player, turn_number):
    """Doesn't use _register_once_per_combat: that helper marks itself 'fired' on the very first..."""
    if turn_number != 1:
        return
    fired = {"done": False}

    def _effect(engine, player, **kwargs):
        if fired["done"] or kwargs.get("source") != "self":
            return
        amount = kwargs.get("amount", 0)
        if amount:
            fired["done"] = True
            player.heal(amount)
            engine.log.append(f"{player.name} heals {amount} HP (Demon Tongue)")

    player.register_hook("hp_lost", _effect)


def _ruined_helmet_start(engine, player, turn_number):
    """Doesn't use _register_once_per_combat, for the same reason as Demon Tongue: it would mark itself..."""
    if turn_number != 1:
        return
    fired = {"done": False}

    def _effect(engine, player, **kwargs):
        if fired["done"] or kwargs.get("status") != StatusType.STRENGTH:
            return
        amount = kwargs.get("amount", 0)
        if amount > 0:
            fired["done"] = True
            player.add_status(StatusType.STRENGTH, amount)
            engine.log.append(f"{player.name} gains {amount} additional Strength (Ruined Helmet)")

    player.register_hook("status_gained", _effect)


def _red_skull_start(engine, player, turn_number):
    if turn_number != 1:
        return
    player.bonus_strength_below_half = 3


def _sturdy_clamp_start(engine, player, turn_number):
    if turn_number != 1:
        return
    player.retain_block_cap = 10


def _ice_cream_start(engine, player, turn_number):
    if turn_number != 1:
        return
    player.conserve_energy = True


def _paper_phrog_start(engine, player, turn_number):
    """"Enemies with Vulnerable take 75% more damage rather than 50%." Vulnerable's own 50% is applied..."""
    if turn_number != 1:
        return
    player.vulnerable_damage_bonus += 0.25


def _shuriken_start(engine, player, turn_number):
    if turn_number != 1:
        return

    def _gain(engine, player):
        player.add_status(StatusType.STRENGTH, 1)
        engine.log.append(f"{player.name} gains 1 Strength (Shuriken)")
    _register_every_n_per_turn(player, "attack_played", 3, _gain)


def _razor_tooth_start(engine, player, turn_number):
    """"Every time you play an Attack or Skill, Upgrade it for the remainder of combat." Routed through..."""
    if turn_number != 1:
        return

    def _cb(engine, player, card=None, **kwargs):
        if card is None or card.card_type not in (CardType.ATTACK, CardType.SKILL):
            return
        if player.upgrade_for_combat(card):
            engine.log.append(f"{card.name} is upgraded for this combat (Razor Tooth)")
    player.register_hook("card_played", _cb)


def _mummified_hand_start(engine, player, turn_number):
    """"Whenever you play a Power, a random card in your Hand is free to play that turn." Needs a..."""
    if turn_number != 1:
        return

    def _cb(engine, player, **kwargs):
        candidates = [c for c in player.hand if c.current_cost() != "X"]
        if not candidates:
            return
        chosen = player.rng.choice(candidates)
        player.set_temp_cost(chosen, 0, scope="turn")
        engine.log.append(f"{chosen.name} is free this turn (Mummified Hand)")
    player.register_hook("power_played", _cb)


def _unsettling_lamp_start(engine, player, turn_number):
    """"Each combat, the first time you play a card that Debuffs an enemy, double its effect." Uses the..."""
    if turn_number != 1:
        return
    state = {"used": False, "busy": False}

    def _cb(engine, player, status=None, amount=0, target=None, **kwargs):
        if state["used"] or state["busy"] or target is None:
            return
        if status not in DEBUFF_STATUSES or amount <= 0:
            return
        state["used"] = True
        state["busy"] = True
        try:
            target.add_status(status, amount)
            engine.log.append(f"{status.name} on {target.name} is doubled (Unsettling Lamp)")
        finally:
            state["busy"] = False
    player.register_hook("status_applied", _cb)


def _gambling_chip_start(engine, player, turn_number):
    """"At the start of each combat, discard any number of cards then draw that many." No UI for the..."""
    if turn_number != 1:
        return
    n = len(player.hand)
    if not n:
        return
    player.discard_pile.extend(player.hand)
    player.hand = []
    engine.draw_extra(player, n)
    engine.log.append(f"{player.name} redraws {n} cards (Gambling Chip)")

RELIC_POOL_IRONCLAD = [
    Relic("Blood Vial", "Common", "At the start of each combat, heal 2 HP.",
          on_turn_start=_blood_vial_start),
    Relic("Anchor", "Common", "Start each combat with 10 Block.",
          on_turn_start=_anchor_start),
    Relic("Vajra", "Common", "Start each combat with 1 Strength.",
          on_turn_start=_vajra_start),
    Relic("Bag of Marbles", "Common", "At the start of each combat, apply 1 Vulnerable to ALL enemies.",
          on_turn_start=_bag_of_marbles_start),
    Relic("Bag of Preparation", "Common", "At the start of each combat, draw 2 additional cards.",
          on_turn_start=_bag_of_preparation_start),
    Relic("Centennial Puzzle", "Common", "The first time you lose HP each combat, draw 3 cards.",
          on_turn_start=_centennial_puzzle_start),
    Relic("Strawberry", "Common", "Upon pickup, raise your Max HP by 7.",
          on_pickup=_strawberry_pickup),
    Relic("Festive Popper", "Common", "At the start of each combat, deal 9 damage to ALL enemies.",
          on_turn_start=_festive_popper_start),
    Relic("Bronze Scales", "Common", "Start each combat with 3 Thorns.",
          on_turn_start=_bronze_scales_start),
    Relic("Gorget", "Common", "At the start of each combat, gain 4 Plating.",
          on_turn_start=_gorget_start),
    Relic("Happy Flower", "Common", "Every 3 turns, gain 1 Energy.",
          on_turn_start=_happy_flower_start),
    Relic("Lantern", "Common", "Start each combat with an additional 1 Energy.",
          on_turn_start=_lantern_start),
    Relic("Oddly Smooth Stone", "Common", "Start each combat with 1 Dexterity.",
          on_turn_start=_oddly_smooth_stone_start),
    Relic("Pendulum", "Common", "Every 3 turns, draw 1 card.",
          on_turn_start=_pendulum_start),
    Relic("Red Mask", "Common", "At the start of combat, apply 1 Weak to ALL enemies.",
          on_turn_start=_red_mask_start),
    Relic("War Paint", "Common", "Upon pickup, Upgrade 2 random Skills.",
          on_pickup=_war_paint_pickup),
    Relic("Whetstone", "Common", "Upon pickup, Upgrade 2 random Attacks.",
          on_pickup=_whetstone_pickup),

    Relic("Akabeko", "Uncommon", "At the start of each combat, gain 8 Vigor.",
          on_turn_start=_akabeko_start),
    Relic("Candelabra", "Uncommon", "At the start of your 2nd turn, gain 2 Energy.",
          on_turn_start=_candelabra_start),
    Relic("Gremlin Horn", "Uncommon", "Whenever an enemy dies, gain 1 Energy and draw 1 card.",
          on_turn_start=_gremlin_horn_start),
    Relic("Horn Cleat", "Uncommon", "At the start of your 2nd turn, gain 14 Block.",
          on_turn_start=_horn_cleat_start),
    Relic("Joss Paper", "Uncommon", "Every 5 times you Exhaust a card, draw 1 card.",
          on_turn_start=_joss_paper_start),
    Relic("Kusarigama", "Uncommon", "Every time you play 3 Attacks in a single turn, deal 6 damage to random.",
          on_turn_start=_kusarigama_start),
    Relic("Letter Opener", "Uncommon", "Every time you play 3 Skills in a single turn, deal 5 damage to ALL.",
          on_turn_start=_letter_opener_start),
    Relic("Mercury Hourglass", "Uncommon", "At the start of your turn, deal 3 damage to ALL enemies.",
          on_turn_start=_mercury_hourglass_start),
    Relic("Nunchaku", "Uncommon", "Every time you play 10 Attacks, gain 1 Energy.",
          on_turn_start=_nunchaku_start),
    Relic("Orichalcum", "Uncommon", "If you end your turn without Block, gain 6 Block.",
          on_turn_end=_orichalcum_end),
    Relic("Ornamental Fan", "Uncommon", "Every time you play 3 Attacks in a single turn, gain 4 Block.",
          on_turn_start=_ornamental_fan_start),
    Relic("Parrying Shield", "Uncommon", "If you end a turn with at least 10 Block, deal 6 damage to random.",
          on_turn_end=_parrying_shield_end),
    Relic("Pear", "Uncommon", "Upon pickup, raise your Max HP by 10.",
          on_pickup=_pear_pickup),
    Relic("Pen Nib", "Uncommon", "Every 10th Attack you play deals double damage.",
          on_turn_start=_pen_nib_start),
    Relic("Permafrost", "Uncommon", "The first time you play a Power each combat, gain 7 Block.",
          on_turn_start=_permafrost_start),
    Relic("Ripple Basin", "Uncommon", "If you did not play any Attacks during your turn, gain 4 Block.",
          on_turn_start=_ripple_basin_start, on_turn_end=_ripple_basin_end),
    Relic("Sparkling Rouge", "Uncommon", "At the start of your 3rd turn, gain 1 Strength and 1 Dexterity.",
          on_turn_start=_sparkling_rouge_start),
    Relic("Stone Cracker", "Uncommon", "At the start of combat, Upgrade 2 random cards in your Draw Pile.",
          on_turn_start=_stone_cracker_start),
    Relic("Tuning Fork", "Uncommon", "Every time you play 10 Skills, gain 7 Block.",
          on_turn_start=_tuning_fork_start),
    Relic("Vambrace", "Uncommon", "The first time you gain Block from a card each combat, double amount.",
          on_turn_start=_vambrace_start),
    Relic("Self-Forming Clay", "Uncommon", "Whenever you lose HP in combat, gain 3 Block next turn.",
          on_turn_start=_self_forming_clay_start),
    Relic("Twisted Funnel", "Uncommon", "At the start of each combat, apply 4 Poison to ALL enemies.",
          on_turn_start=_twisted_funnel_start),

    Relic("Art of War", "Rare", "If you do not play any Attacks during your turn, gain an additional Energy next turn.",
          on_turn_start=_art_of_war_start, on_turn_end=_art_of_war_end),
    Relic("Beating Remnant", "Rare", "You cannot lose more than 20 HP in a single turn.",
          on_turn_start=_beating_remnant_start, on_turn_end=_beating_remnant_end),
    Relic("Bellows", "Rare", "The first Hand you draw each combat is Upgraded.",
          on_turn_start=_bellows_start),
    Relic("Captain's Wheel", "Rare", "At the start of your 3rd turn, gain 18 Block.",
          on_turn_start=_captains_wheel_start),
    Relic("Chandelier", "Rare", "At the start of your 3rd turn, gain 3 Energy.",
          on_turn_start=_chandelier_start),
    Relic("Cloak Clasp", "Rare", "At the end of your turn, gain 1 Block for each card in your Hand.",
          on_turn_end=_cloak_clasp_end),
    Relic("Frozen Egg", "Rare", "Whenever you add a Power into your Deck, Upgrade it.",
          on_card_added=_frozen_egg_added),
    Relic("Game Piece", "Rare", "Whenever you play a Power, draw 1 card.",
          on_turn_start=_game_piece_start),
    Relic("Intimidating Helmet", "Rare", "Whenever you play a card that costs 2 or more Energy, gain 4 Block.",
          on_turn_start=_intimidating_helmet_start),
    Relic("Kunai", "Rare", "Every time you play 3 Attacks in a single turn, gain 1 Dexterity.",
          on_turn_start=_kunai_start),
    Relic("Lizard Tail", "Rare", "When your HP would be reduced to 0, heal to 50% of your Max HP instead (works once).",
          on_turn_start=_lizard_tail_start),
    Relic("Mango", "Rare", "Upon pickup, raise your Max HP by 14.",
          on_pickup=_mango_pickup),
    Relic("Meat on the Bone", "Rare", "If your HP is at or below 50% at the end of combat, heal 12 HP.",
          on_combat_end=_meat_on_the_bone_end),
    Relic("Molten Egg", "Rare", "Whenever you add an Attack card to your Deck, Upgrade it.",
          on_card_added=_molten_egg_added),
    Relic("Pocketwatch", "Rare", "Whenever you play 3 or fewer cards during your turn, draw 3 additional cards at the start of your next turn.",
          on_turn_start=_pocketwatch_start, on_turn_end=_pocketwatch_end),
    Relic("Prayer Wheel", "Rare", "Normal enemies drop an additional card reward."),
    Relic("Rainbow Ring", "Rare", "The first time you play an Attack, Skill, and Power each turn, gain 1 Strength and 1 Dexterity.",
          on_turn_start=_rainbow_ring_start),
    Relic("Stone Calendar", "Rare", "At the end of turn 7, deal 52 damage to ALL enemies.",
          on_turn_end=_stone_calendar_end),
    Relic("Toxic Egg", "Rare", "Whenever you add a Skill into your Deck, Upgrade it.",
          on_card_added=_toxic_egg_added),
    Relic("Tungsten Rod", "Rare", "Whenever you would lose HP, lose 1 less.",
          on_turn_start=_tungsten_rod_start),
    Relic("Unceasing Top", "Rare", "Whenever you have no cards in Hand during your turn, draw a card.",
          on_turn_start=_unceasing_top_start),
    Relic("Vexing Puzzlebox", "Rare", "At the start of each combat, add a random card into your Hand. It's free to play this turn.",
          on_turn_start=_vexing_puzzlebox_start),

    Relic("Charon's Ashes", "Rare (Ironclad)", "Whenever you Exhaust a card, deal 3 damage to ALL enemies.",
          on_turn_start=_charons_ashes_start),
    Relic("Demon Tongue", "Rare (Ironclad)", "The first time you lose HP on your turn, heal HP equal to the amount lost.",
          on_turn_start=_demon_tongue_start),
    Relic("Ruined Helmet", "Rare (Ironclad)", "The first time you gain Strength each combat, double the amount gained.",
          on_turn_start=_ruined_helmet_start),
]


def _potion_belt_pickup(player):
    player.potion_slots += 2


def _petrified_toad_start(engine, player, turn_number):
    if turn_number != 1:
        return
    if len(player.potions) < player.potion_slots:
        player.potions.append(POTION_SHAPED_ROCK)
        engine.log.append(f"{player.name} procures a Potion-Shaped Rock (Petrified Toad)")


def _reptile_trinket_start(engine, player, turn_number):
    if turn_number != 1:
        return

    def _effect(engine, player, **kwargs):
        player.add_status(StatusType.STRENGTH_THIS_TURN, 3)
        engine.log.append(f"{player.name} gains 3 Strength this turn (Reptile Trinket)")

    player.register_hook("use_potion", _effect)


RELIC_POOL_IRONCLAD += [
    Relic("Potion Belt", "Common", "Upon pickup, gain 2 potion slots.",
          on_pickup=_potion_belt_pickup),
    Relic("Petrified Toad", "Uncommon", "At the start of each combat, procure a Potion-Shaped Rock.",
          on_turn_start=_petrified_toad_start),
    Relic("Reptile Trinket", "Uncommon", "Whenever you use a Potion, gain 3 Strength this turn.",
          on_turn_start=_reptile_trinket_start),
    Relic("White Beast Statue", "Rare", "Potion always appear in combat rewards."),
]


def _pantograph_start(engine, player, turn_number):
    """Wiki: "At the start of each Boss combat, heal 25 HP." Fires on turn 1 only -- "start of combat"..."""
    if turn_number != 1 or not engine.has_enemy_category("boss"):
        return
    before = player.hp
    player.heal(25)
    engine.log.append(f"{player.name} heals {player.hp - before} HP (Pantograph, boss combat)")


def _book_of_five_rings_added(player, card):
    """Wiki: "Every 5 cards you add to your Deck, heal 20 HP." Counter lives in relic_counters, which..."""
    player.relic_counters["book_of_five_rings"] = \
        player.relic_counters.get("book_of_five_rings", 0) + 1
    if player.relic_counters["book_of_five_rings"] % 5 == 0:
        player.heal(20)


RELIC_POOL_IRONCLAD += [
    Relic("Book of Five Rings", "Common", "Every 5 cards you add to your Deck, heal 20 HP.",
          on_card_added=_book_of_five_rings_added),
    Relic("Pantograph", "Uncommon", "At the start of each Boss combat, heal 25 HP.",
          on_turn_start=_pantograph_start),
    Relic("White Star", "Rare", "Elites drop an additional Rare card reward."),
    Relic("Strike Dummy", "Common", "Cards containing \"Strike\" deal 3 additional damage."),
    Relic("Red Skull", "Common (Ironclad)", "While your HP is at or below 50%, you have 3 additional Strength.",
          on_turn_start=_red_skull_start),
    Relic("Miniature Cannon", "Uncommon", "Upgraded Attacks deal 3 additional damage."),
    Relic("Paper Phrog", "Uncommon (Ironclad)", "Enemies with Vulnerable take 75% more damage rather than 50%.",
          on_turn_start=_paper_phrog_start),
    Relic("Shuriken", "Rare", "Every time you play 3 Attacks in a single turn, gain 1 Strength.",
          on_turn_start=_shuriken_start),
    Relic("Sturdy Clamp", "Rare", "Up to 10 Block persists across turns.",
          on_turn_start=_sturdy_clamp_start),
    Relic("Ice Cream", "Rare", "Energy is now conserved between turns.",
          on_turn_start=_ice_cream_start),
    Relic("Mummified Hand", "Rare", "Whenever you play a Power, a random card in your Hand is free to play that turn.",
          on_turn_start=_mummified_hand_start),
    Relic("Razor Tooth", "Rare", "Every time you play an Attack or Skill, Upgrade it for the remainder of combat.",
          on_turn_start=_razor_tooth_start),
    Relic("Unsettling Lamp", "Rare", "Each combat, the first time you play a card that Debuffs an enemy, double its effect.",
          on_turn_start=_unsettling_lamp_start),
    Relic("Gambling Chip", "Rare", "At the start of each combat, discard any number of cards then draw that many.",
          on_turn_start=_gambling_chip_start),
]


ALL_RELICS = sorted({r.name for r in RELIC_POOL_IRONCLAD} | {BURNING_BLOOD.name})
RELIC_IDS = {name: i for i, name in enumerate(ALL_RELICS)}
TOTAL_RELIC_IDS = len(RELIC_IDS)


def relic_id(relic) -> int:
    return RELIC_IDS.get(relic.name, -1)
