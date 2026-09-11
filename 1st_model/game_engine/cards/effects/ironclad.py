"""What each Ironclad card does."""

from typing import Callable, Dict, List, Optional, Union
import copy

from ...entities import HAND_LIMIT
from ...statuses import StatusType, DEBUFF_STATUSES
from ..model import Card, CardType, TargetMode, UNPLAYABLE
from .common import *  # noqa: F401,F403
from .common import (_ally_of, _arm_once, _arm_power,
                     _auto_target_for, _fresh_free_card, _pick,
                     _return_next_turn, _sample_distinct)


def fx_defend(engine, caster, target, card, x_amount=0):
    gained = caster.gain_block(card.val("block") + caster.defend_block_bonus)
    engine.log.append(f"{caster.name} gains {gained} block ({card.name})")


def fx_iron_wave(engine, caster, target, card, x_amount=0):
    caster.gain_block(card.val("block"))
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_shrug_it_off(engine, caster, target, card, x_amount=0):
    caster.gain_block(card.val("block"))
    engine.draw_extra(caster, card.val("cards", 1))


def fx_true_grit(engine, caster, target, card, x_amount=0):
    """Real STS2 True Grit: Gain Block. Exhaust 1 card at random (upgraded: chosen)."""
    caster.gain_block(card.val("block"))
    hand = [c for c in caster.hand if c is not card]
    if hand:
        chosen = (engine.request_choice(caster, hand, "Exhaust a card", "exhaust")
                  if card.upgraded else caster.rng.choice(hand))
        engine.exhaust_card(caster, chosen)


def fx_battle_trance(engine, caster, target, card, x_amount=0):
    """Draw N cards. You cannot draw additional cards this turn."""
    engine.draw_extra(caster, card.val("cards"))
    caster.no_more_draw_this_turn = True


def fx_whirlwind(engine, caster, target, card, x_amount=0):
    """X-cost: deal damage to ALL enemies, X times (X = energy spent)."""
    times = x_amount
    dmg_base = card.val("damage")
    for _ in range(times):
        for e in engine.enemies_alive():
            dmg = caster.deal_attack_damage(dmg_base)
            e.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_blaze(engine, caster, target, card, x_amount=0):
    """Give another player Strength."""
    ally = target if target is not None else engine.other_player(caster)
    if ally is None:
        engine.log.append(f"{card.name} has no ally to target, fizzles")
        return
    amt = card.val("strength")
    ally.add_status(StatusType.STRENGTH, amt)
    engine.log.append(f"{caster.name} gives {ally.name} {amt} strength ({card.name})")


def fx_demonic_shield(engine, caster, target, card, x_amount=0):
    """Lose 1 HP. Give another player Block equal to your Block. (Exhausts unless upgraded.)"""
    caster.lose_hp(card.val("hploss", 1), log=engine.log, label=card.name)
    ally = target if target is not None else engine.other_player(caster)
    if ally is None:
        engine.log.append(f"{card.name} has no ally to target, fizzles")
        return
    gained = ally.gain_block(caster.block)
    engine.log.append(f"{caster.name} gives {ally.name} {gained} block ({card.name})")


def fx_tank(engine, caster, target, card, x_amount=0):
    """Take 50% additional damage from enemies."""
    caster.add_status(StatusType.TANK_SELF, 1)
    for p in engine.players:
        if p is not caster and p.alive:
            p.add_status(StatusType.TANK_ALLY, 1)
    engine.log.append(f"{caster.name} becomes the Tank ({card.name})")


def fx_anger(engine, caster, target, card, x_amount=0):
    """Deal damage."""
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    clone = card.clone()
    caster.discard_pile.append(clone)
    engine.log.append(f"{caster.name} adds a copy of {card.name} to discard pile")


def fx_armaments(engine, caster, target, card, x_amount=0):
    """Gain Block."""
    gained = caster.gain_block(card.val("block"))
    engine.log.append(f"{caster.name} gains {gained} block ({card.name})")
    candidates = [c for c in caster.hand if not c.upgraded]
    if not candidates:
        return
    if card.upgraded:
        for c in candidates:
            caster.upgrade_for_combat(c)
        engine.log.append(f"{caster.name} upgrades all cards in hand ({card.name})")
    else:
        chosen = engine.request_choice(caster, candidates,
                                        "Upgrade a card in your Hand", "upgrade")
        caster.upgrade_for_combat(chosen)
        engine.log.append(f"{caster.name} upgrades {chosen.name} ({card.name})")


def fx_blood_wall(engine, caster, target, card, x_amount=0):
    caster.lose_hp(card.val("hploss", 2), log=engine.log, label=card.name)
    caster.gain_block(card.val("block"))


def fx_body_slam(engine, caster, target, card, x_amount=0):
    """Deal damage equal to your current Block."""
    dmg = caster.deal_attack_damage(caster.block)
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_breakthrough(engine, caster, target, card, x_amount=0):
    caster.lose_hp(card.val("hploss", 1), log=engine.log, label=card.name)
    for e in engine.enemies_alive():
        dmg = caster.deal_attack_damage(card.val("damage"))
        e.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_cinder(engine, caster, target, card, x_amount=0):
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    hand = [c for c in caster.hand if c is not card]
    if hand:
        engine.exhaust_card(caster, caster.rng.choice(hand))


def fx_headbutt(engine, caster, target, card, x_amount=0):
    """Deal damage."""
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    if caster.discard_pile:
        chosen = engine.request_choice(caster, caster.discard_pile,
                                        "Put a card on top of your Draw Pile",
                                        "to_draw_top")
        caster.discard_pile.remove(chosen)
        caster.draw_pile.append(chosen)
        engine.log.append(f"{caster.name} puts {chosen.name} on top of the draw pile ({card.name})")


def fx_molten_fist(engine, caster, target, card, x_amount=0):
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    current_vuln = target.get_status(StatusType.VULNERABLE)
    if current_vuln > 0:
        target.add_status(StatusType.VULNERABLE, current_vuln, applier=caster)
        engine.log.append(f"{target.name}'s vulnerable is doubled ({card.name})")


def fx_perfected_strike(engine, caster, target, card, x_amount=0):
    """Extra damage per card containing 'Strike' in the caster's WHOLE deck (not just hand) -- matches..."""
    strike_count = sum(1 for c in caster.deck_template if "Strike" in c.name)
    extra = card.val("extradamage") * strike_count
    dmg = caster.deal_attack_damage(card.val("damage") + extra)
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_pommel_strike(engine, caster, target, card, x_amount=0):
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    engine.draw_extra(caster, card.val("cards"))


def fx_setup_strike(engine, caster, target, card, x_amount=0):
    """Deal damage, THEN gain Strength for the rest of this turn only (doesn't buff this card's own..."""
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    caster.add_status(StatusType.STRENGTH_THIS_TURN, card.val("strength"))


def fx_sword_boomerang(engine, caster, target, card, x_amount=0):
    times = card.val("repeat")
    for _ in range(times):
        alive = engine.enemies_alive()
        if not alive:
            break
        victim = caster.rng.choice(alive)
        dmg = caster.deal_attack_damage(card.val("damage"))
        victim.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_taunt(engine, caster, target, card, x_amount=0):
    caster.gain_block(card.val("block"))
    target.add_status(StatusType.VULNERABLE, card.val("vulnerable"), applier=caster)


def fx_thunderclap(engine, caster, target, card, x_amount=0):
    for e in engine.enemies_alive():
        dmg = caster.deal_attack_damage(card.val("damage"))
        e.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
        e.add_status(StatusType.VULNERABLE, card.val("vulnerable", 1), applier=caster)


def fx_tremble(engine, caster, target, card, x_amount=0):
    target.add_status(StatusType.VULNERABLE, card.val("vulnerable"), applier=caster)


def fx_twin_strike(engine, caster, target, card, x_amount=0):
    for _ in range(2):
        dmg = caster.deal_attack_damage(card.val("damage"))
        target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_havoc(engine, caster, target, card, x_amount=0):
    """Play the top card of your Draw Pile and Exhaust it."""
    played = caster.take_top_of_draw(engine.log)
    if played is None:
        engine.log.append(f"{card.name} finds no card to play")
        return
    engine.log.append(f"{card.name} plays {played.name} from the draw pile")
    resolvable, auto_target = _auto_target_for(engine, caster, played)
    if resolvable:
        engine.resolve_card_effect(caster, played, auto_target)
    else:
        engine.log.append(f"{played.name} has nothing left to hit")
    engine.exhaust_card(caster, played)


def fx_dark_embrace(engine, caster, target, card, x_amount=0):
    """Power: Whenever a card is Exhausted, draw 1 card."""
    def _on_exhaust(engine, player, card=None, **kw):
        engine.draw_extra(player, 1)
        engine.log.append(f"{player.name} draws a card (Dark Embrace trigger)")
    caster.register_hook("card_exhausted", _on_exhaust)
    engine.log.append(f"{caster.name} gains Dark Embrace")


def fx_feel_no_pain(engine, caster, target, card, x_amount=0):
    """Power: Whenever a card is Exhausted, gain Block."""
    block_amt = card.val("block")

    def _on_exhaust(engine, player, card=None, **kw):
        player.gain_block(block_amt)
        engine.log.append(f"{player.name} gains {block_amt} block (Feel No Pain trigger)")
    caster.register_hook("card_exhausted", _on_exhaust)
    engine.log.append(f"{caster.name} gains Feel No Pain")


def fx_rage(engine, caster, target, card, x_amount=0):
    """Skill (not Power, per the sheet) but still a trigger: whenever you play an Attack THIS TURN..."""
    block_amt = card.val("block")

    def _on_attack(engine, player, card=None, **kw):
        player.gain_block(block_amt)
        engine.log.append(f"{player.name} gains {block_amt} block (Rage trigger)")
    caster.register_hook("attack_played", _on_attack, expires_this_turn=True)
    engine.log.append(f"{caster.name} is enraged this turn (Rage)")


def fx_bloodletting(engine, caster, target, card, x_amount=0):
    caster.lose_hp(card.val("hploss", 3), log=engine.log, label=card.name)
    caster.energy += card.val("energy")


def fx_bully(engine, caster, target, card, x_amount=0):
    vuln = target.get_status(StatusType.VULNERABLE)
    extra = card.val("extradamage") * vuln
    dmg = caster.deal_attack_damage(card.val("damage") + extra)
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_dismantle(engine, caster, target, card, x_amount=0):
    hits = 2 if target.get_status(StatusType.VULNERABLE) > 0 else 1
    for _ in range(hits):
        if not target.alive:
            break
        dmg = caster.deal_attack_damage(card.val("damage"))
        target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_evil_eye(engine, caster, target, card, x_amount=0):
    gained = caster.gain_block(card.val("block"))
    engine.log.append(f"{caster.name} gains {gained} block ({card.name})")
    if caster.exhausted_this_turn:
        gained2 = caster.gain_block(card.val("block"))
        engine.log.append(f"{caster.name} gains {gained2} additional block, having Exhausted this turn ({card.name})")


def fx_expect_a_fight(engine, caster, target, card, x_amount=0):
    strength = caster.get_status(StatusType.STRENGTH)
    total = card.val("block") + card.val("extrablock") * strength
    gained = caster.gain_block(total)
    engine.log.append(f"{caster.name} gains {gained} block ({card.name})")


def fx_fight_me(engine, caster, target, card, x_amount=0):
    for _ in range(2):
        dmg = caster.deal_attack_damage(card.val("damage"))
        target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    caster.add_status(StatusType.STRENGTH, card.val("strength"))
    target.add_status(StatusType.STRENGTH, 1)


def fx_hemokinesis(engine, caster, target, card, x_amount=0):
    caster.lose_hp(card.val("hploss", 2), log=engine.log, label=card.name)
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_inflame(engine, caster, target, card, x_amount=0):
    """Power in name only, per the real card -- an instant permanent Strength gain with no ongoing..."""
    caster.add_status(StatusType.STRENGTH, card.val("strength"))
    engine.log.append(f"{caster.name} gains {card.val('strength')} strength ({card.name})")


def fx_outrage(engine, caster, target, card, x_amount=0):
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    for p in engine.players:
        if p.alive:
            p.discard_pile.append(card.clone())
    engine.log.append(f"a copy of {card.name} is added to everyone's discard pile")


def fx_spite(engine, caster, target, card, x_amount=0):
    """Unlike Twin Strike/Fight Me!/Thrash (whose upgrade only raises damage, leaving the hit count at..."""
    hits = card.val("hits") if caster.lost_hp_this_turn > 0 else 1
    for _ in range(hits):
        if not target.alive:
            break
        dmg = caster.deal_attack_damage(card.val("damage"))
        target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_stone_armor(engine, caster, target, card, x_amount=0):
    caster.add_status(StatusType.PLATED_ARMOR, card.val("plating"))
    engine.log.append(f"{caster.name} gains {card.val('plating')} Plating ({card.name})")


def fx_uppercut(engine, caster, target, card, x_amount=0):
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    target.add_status(StatusType.WEAK, card.val("weak"))
    target.add_status(StatusType.VULNERABLE, card.val("vulnerable"), applier=caster)


def fx_ashen_strike(engine, caster, target, card, x_amount=0):
    extra = card.val("extradamage") * len(caster.exhaust_pile)
    dmg = caster.deal_attack_damage(card.val("damage") + extra)
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_infernal_blade(engine, caster, target, card, x_amount=0):
    """Same disposable-instance trick as the Vexing Puzzlebox relic / Attack Potion: a fresh Card, cost..."""
    # Deferred: pools builds its tables OUT of these effects,
    # so importing it at module level would be a cycle.
    from ..pools import FACTORIES_BY_TYPE
    candidates = FACTORIES_BY_TYPE.get(CardType.ATTACK, ())
    if not candidates:
        return
    new_card = caster.rng.choice(candidates)()
    new_card.cost = 0
    caster.add_to_hand(new_card, engine.log)
    engine.log.append(f"{caster.name} adds {new_card.name} (free this turn) to their Hand ({card.name})")


def fx_second_wind(engine, caster, target, card, x_amount=0):
    non_attacks = [c for c in caster.hand if c.card_type != CardType.ATTACK]
    for c in non_attacks:
        engine.exhaust_card(caster, c)
    if non_attacks:
        gained = caster.gain_block(card.val("block") * len(non_attacks))
        engine.log.append(f"{caster.name} gains {gained} block for {len(non_attacks)} Exhausted cards ({card.name})")


def fx_rupture(engine, caster, target, card, x_amount=0):
    """Power: whenever you lose HP ON YOUR TURN, gain Strength."""
    amt = card.val("strength")

    def _on_hp_lost(engine, player, **kwargs):
        if kwargs.get("source") != "self":
            return
        player.add_status(StatusType.STRENGTH, amt)
        engine.log.append(f"{player.name} gains {amt} strength (Rupture trigger)")
    caster.register_hook("hp_lost", _on_hp_lost)
    engine.log.append(f"{caster.name} gains Rupture")


def fx_inferno(engine, caster, target, card, x_amount=0):
    """Power: at the start of your turn, lose 1 HP."""
    dmg_amt = card.val("damage")

    def _on_turn_start(engine, player, **kwargs):
        player.lose_hp(1, log=engine.log, label=card.name)

    def _on_hp_lost(engine, player, **kwargs):
        if kwargs.get("source") != "self":
            return
        for e in engine.enemies_alive():
            dmg = player.deal_attack_damage(dmg_amt)
            e.take_damage(dmg, log=engine.log, label=f"{card.name} trigger", attacker=player)
    caster.register_hook("turn_start", _on_turn_start)
    caster.register_hook("hp_lost", _on_hp_lost)
    engine.log.append(f"{caster.name} gains Inferno")


def fx_burning_pact(engine, caster, target, card, x_amount=0):
    """No UI to choose which card to Exhaust, so auto-picks the first (same simplification as Armaments)."""
    hand = [c for c in caster.hand if c is not card]
    if hand:
        engine.exhaust_card(caster, hand[0])
    engine.draw_extra(caster, card.val("cards"))


def fx_drum_of_battle(engine, caster, target, card, x_amount=0):
    """Draw now."""
    engine.draw_extra(caster, card.val("cards"))
    energy_amt = card.val("energy")

    if id(card) in caster.armed_card_hooks:
        return
    caster.armed_card_hooks.add(id(card))

    def _on_exhaust(engine, player, card=None, **kw):
        if card is not this_card:
            return
        player.energy += energy_amt
        engine.log.append(f"{player.name} gains {energy_amt} energy (Drum of Battle trigger)")
    this_card = card
    caster.register_hook("card_exhausted", _on_exhaust)


def fx_barricade(engine, caster, target, card, x_amount=0):
    caster.retain_block = True
    engine.log.append(f"{caster.name}'s Block will no longer be removed at the start of turn ({card.name})")


def fx_cascade(engine, caster, target, card, x_amount=0):
    """X-cost: play the top X (or X+1 upgraded) cards of the Draw Pile, reusing Havoc's..."""
    times = x_amount
    if card.upgraded:
        times += 1
    for _ in range(times):
        played = caster.take_top_of_draw(engine.log)
        if played is None:
            break
        engine.log.append(f"{card.name} plays {played.name} from the draw pile")
        resolvable, auto_target = _auto_target_for(engine, caster, played)
        if resolvable:
            engine.resolve_card_effect(caster, played, auto_target)
        else:
            engine.log.append(f"{played.name} has nothing left to hit")
            caster.discard_pile.append(played)
            break
        if played.exhausts_now():
            engine.exhaust_card(caster, played)
        else:
            caster.discard_pile.append(played)


def fx_conflagration(engine, caster, target, card, x_amount=0):
    times = card.val("repeat")
    dmg_base = card.val("damage")
    for _ in range(times):
        for e in engine.enemies_alive():
            dmg = caster.deal_attack_damage(dmg_base)
            e.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_crimson_mantle(engine, caster, target, card, x_amount=0):
    """Power: at the start of your turn, lose 1 HP and gain Block."""
    block_amt = card.val("block")

    def _on_turn_start(engine, player, **kwargs):
        player.lose_hp(1, log=engine.log, label=card.name)
        gained = player.gain_block(block_amt)
        engine.log.append(f"{player.name} gains {gained} block (Crimson Mantle trigger)")
    caster.register_hook("turn_start", _on_turn_start)
    engine.log.append(f"{caster.name} gains Crimson Mantle")


def fx_demon_form(engine, caster, target, card, x_amount=0):
    """Power: at the start of your turn, gain Strength."""
    amt = card.val("strength")

    def _on_turn_start(engine, player, **kwargs):
        player.add_status(StatusType.STRENGTH, amt)
        engine.log.append(f"{player.name} gains {amt} strength (Demon Form trigger)")
    caster.register_hook("turn_start", _on_turn_start)
    engine.log.append(f"{caster.name} gains Demon Form")


def fx_not_yet(engine, caster, target, card, x_amount=0):
    before = caster.hp
    caster.heal(card.val("heal"))
    engine.log.append(f"{caster.name} heals {caster.hp - before} HP ({card.name})")


def fx_offering(engine, caster, target, card, x_amount=0):
    caster.lose_hp(card.val("hploss", 6), log=engine.log, label=card.name)
    caster.energy += card.val("energy")
    engine.draw_extra(caster, card.val("cards"))


def fx_pacts_end(engine, caster, target, card, x_amount=0):
    if len(caster.exhaust_pile) < 3:
        return
    for e in engine.enemies_alive():
        dmg = caster.deal_attack_damage(card.val("damage"))
        e.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_pyre(engine, caster, target, card, x_amount=0):
    """Power: gain Energy at the start of each turn (including the turn it's played on?"""
    amt = card.val("energy")

    def _on_turn_start(engine, player, **kwargs):
        player.energy += amt
        engine.log.append(f"{player.name} gains {amt} energy (Pyre trigger)")
    caster.register_hook("turn_start", _on_turn_start)
    engine.log.append(f"{caster.name} gains Pyre")


def fx_tear_asunder(engine, caster, target, card, x_amount=0):
    hits = 1 + caster.hp_loss_events_this_combat
    for _ in range(hits):
        if not target.alive:
            break
        dmg = caster.deal_attack_damage(card.val("damage"))
        target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_juggernaut(engine, caster, target, card, x_amount=0):
    """Power: whenever you gain Block, deal damage to a random enemy."""
    dmg_amt = card.val("damage")

    def _on_block_gained(engine, player, **kwargs):
        alive = engine.enemies_alive()
        if not alive:
            return
        victim = player.rng.choice(alive)
        dmg = player.deal_attack_damage(dmg_amt)
        victim.take_damage(dmg, log=engine.log, label=f"{card.name} trigger", attacker=player)
    caster.register_hook("block_gained", _on_block_gained)
    engine.log.append(f"{caster.name} gains Juggernaut")


def fx_fiend_fire(engine, caster, target, card, x_amount=0):
    hand = [c for c in caster.hand if c is not card]
    for c in hand:
        engine.exhaust_card(caster, c)
    count = len(hand)
    dmg_base = card.val("damage")
    for _ in range(count):
        if not target.alive:
            break
        dmg = caster.deal_attack_damage(dmg_base)
        target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_unmovable(engine, caster, target, card, x_amount=0):
    """Power: the first time you gain Block from a card each turn, double the amount gained."""
    fired_this_turn = {"done": False}

    def _on_turn_start(engine, player, **kwargs):
        fired_this_turn["done"] = False
    caster.register_hook("turn_start", _on_turn_start)

    def _on_block_gained(engine, player, **kwargs):
        if fired_this_turn["done"]:
            return
        amount = kwargs.get("amount", 0)
        if amount:
            fired_this_turn["done"] = True
            player.block += amount
            engine.log.append(f"{player.name} gains {amount} additional block (Unmovable trigger)")
    caster.register_hook("block_gained", _on_block_gained)
    engine.log.append(f"{caster.name} gains Unmovable")


def fx_thrash(engine, caster, target, card, x_amount=0):
    """Exhaust a random Attack from Hand and add ITS damage to this card's damage -- for this single..."""
    attacks = [c for c in caster.hand if c is not card and c.card_type == CardType.ATTACK]
    bonus = 0
    if attacks:
        chosen = caster.rng.choice(attacks)
        bonus = chosen.val("damage")
        engine.exhaust_card(caster, chosen)
        engine.log.append(f"{caster.name} exhausts {chosen.name}, adding {bonus} damage to {card.name}")
    for _ in range(2):
        dmg = caster.deal_attack_damage(card.val("damage") + bonus)
        target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_feed(engine, caster, target, card, x_amount=0):
    """If the hit is fatal, raise Max HP. take_damage() already returns a killed flag on its..."""
    dmg = caster.deal_attack_damage(card.val("damage"))
    result = target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    if result.killed:
        gain = card.val("maxhp")
        caster.max_hp += gain
        caster.hp += gain
        engine.log.append(f"{caster.name}'s Max HP rises by {gain} ({card.name}, enemy defeated)")


def fx_pillage(engine, caster, target, card, x_amount=0):
    """Draw cards until a non-Attack is drawn."""
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    while True:
        before = len(caster.hand)
        caster.draw_cards(1, engine.log)
        if len(caster.hand) <= before:
            break
        if caster.hand[-1].card_type != CardType.ATTACK:
            break


def fx_rampage(engine, caster, target, card, x_amount=0):
    """Deal damage (base + this instance's accumulated bonus), then grow that bonus for the rest of..."""
    dmg = caster.deal_attack_damage(card.val("damage") + card.combat_bonus_damage)
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    card.combat_bonus_damage += card.val("increase")
    engine.log.append(f"{card.name}'s damage increases by {card.val('increase')} this combat "
                       f"(now +{card.combat_bonus_damage} total)")


def fx_aggression(engine, caster, target, card, x_amount=0):
    """Power: at the start of your turn, put a random Attack from your Discard Pile into your Hand and..."""
    def _on_turn_start(engine, player, **kw):
        attacks = [c for c in player.discard_pile if c.card_type == CardType.ATTACK]
        if not attacks:
            return
        chosen = player.rng.choice(attacks)
        player.discard_pile.remove(chosen)
        player.upgrade_for_combat(chosen)
        player.add_to_hand(chosen, engine.log)
        engine.log.append(
            f"{player.name} pulls {chosen.name} from the discard pile and upgrades it ({card.name})")
    if _arm_once(caster, card, "turn_start", _on_turn_start):
        engine.log.append(f"{caster.name} gains Aggression")


def fx_brand(engine, caster, target, card, x_amount=0):
    """Lose 1 HP."""
    caster.lose_hp(1, log=engine.log, label=card.name)
    hand = [c for c in caster.hand if c is not card]
    if hand:
        engine.exhaust_card(caster, hand[0])
    amt = card.val("strength")
    caster.add_status(StatusType.STRENGTH, amt)
    engine.log.append(f"{caster.name} gains {amt} strength ({card.name})")


def fx_colossus(engine, caster, target, card, x_amount=0):
    """Gain Block."""
    gained = caster.gain_block(card.val("block"))
    caster.vulnerable_attacker_reduction = 0.5
    engine.log.append(
        f"{caster.name} gains {gained} block and takes 50% less from Vulnerable enemies this turn ({card.name})")


def fx_corruption(engine, caster, target, card, x_amount=0):
    """Ancient Power: Skills cost 0."""
    caster.skills_cost_zero = True
    caster.exhaust_skills = True
    engine.log.append(f"{caster.name} gains Corruption (Skills cost 0 and Exhaust)")


def fx_cruelty(engine, caster, target, card, x_amount=0):
    """Power: Vulnerable enemies take an additional 25%/50% damage."""
    bonus = card.val("bonus_pct") / 100.0
    caster.vulnerable_damage_bonus += bonus
    engine.log.append(
        f"{caster.name} gains Cruelty (+{int(bonus*100)}% damage to Vulnerable enemies)")


def fx_dominate(engine, caster, target, card, x_amount=0):
    """Apply Vulnerable, then gain 1 Strength for each Vulnerable on the enemy -- counted AFTER this..."""
    vuln = card.val("vulnerable")
    target.add_status(StatusType.VULNERABLE, vuln, applier=caster)
    stacks = target.get_status(StatusType.VULNERABLE)
    caster.add_status(StatusType.STRENGTH, stacks)
    engine.log.append(
        f"{caster.name} applies {vuln} vulnerable and gains {stacks} strength ({card.name})")


def fx_flame_barrier(engine, caster, target, card, x_amount=0):
    """Gain Block."""
    gained = caster.gain_block(card.val("block"))
    thorns = card.val("thorns")
    caster.add_status(StatusType.THORNS_THIS_TURN, thorns)
    engine.log.append(
        f"{caster.name} gains {gained} block and {thorns} Thorns this turn ({card.name})")


def fx_grapple(engine, caster, target, card, x_amount=0):
    """Deal damage."""
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    follow_up = card.val("followup")
    victim = target

    def _on_block_gained(engine, player, **kw):
        enemy = victim if victim.alive else None
        if enemy is None:
            alive = engine.enemies_alive()
            if not alive:
                return
            enemy = alive[0]
        hit = player.deal_attack_damage(follow_up)
        enemy.take_damage(hit, log=engine.log, label=f"{card.name} trigger", attacker=player)
    caster.register_hook("block_gained", _on_block_gained, expires_this_turn=True)


def fx_hellraiser(engine, caster, target, card, x_amount=0):
    """Power: whenever you draw a card containing "Strike", it is played against a random enemy."""
    def _on_card_drawn(engine, player, card=None, **kw):
        if card is None or "Strike" not in card.name:
            return
        victim = engine.random_alive_enemy(player)
        if victim is None:
            return
        engine.auto_play_card(player, card, target=victim, source="Hellraiser")
    if _arm_once(caster, card, "card_drawn", _on_card_drawn):
        engine.log.append(f"{caster.name} gains Hellraiser")


def fx_howl_from_beyond(engine, caster, target, card, x_amount=0):
    """Deal damage to ALL enemies."""
    dmg_base = card.val("damage")
    for e in engine.enemies_alive():
        dmg = caster.deal_attack_damage(dmg_base)
        e.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    this_card = card

    def _on_turn_end(engine, player, **kw):
        if this_card not in player.exhaust_pile:
            return
        engine.auto_play_card(player, this_card, source="Howl from Beyond",
                              from_exhaust=True)
    _arm_once(caster, card, "turn_end", _on_turn_end)


def fx_juggling(engine, caster, target, card, x_amount=0):
    """Power: add a copy of the third Attack you play each turn into your Hand."""
    def _on_attack_played(engine, player, card=None, **kw):
        if card is None or player.attacks_played_this_turn != 3:
            return
        player.add_to_hand(card.clone(), engine.log)
        engine.log.append(f"{player.name} adds a copy of {card.name} to hand (Juggling)")
    if _arm_once(caster, card, "attack_played", _on_attack_played):
        engine.log.append(f"{caster.name} gains Juggling")


def fx_mangle(engine, caster, target, card, x_amount=0):
    """Deal damage."""
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    loss = card.val("strength_loss")
    target.add_status(StatusType.STRENGTH_LOSS_THIS_TURN, loss, applier=caster)
    engine.log.append(f"{target.name} loses {loss} strength this turn ({card.name})")


def _midnight_cost(card, player):
    """Costs 1 less for each card Exhausted this combat by ANYONE."""
    engine = getattr(player, "engine", None)
    exhausted = getattr(engine, "total_exhausted_this_combat", 0) if engine else 0
    base = card.upgrade_cost if (card.upgraded and card.upgrade_cost is not None) else card.cost
    return max(0, base - exhausted)


def fx_one_two_punch(engine, caster, target, card, x_amount=0):
    """This turn, your next 1 (or 2) Attacks are played an extra time."""
    n = card.val("replays")
    caster.extra_attack_plays += n
    engine.log.append(f"{caster.name}'s next {n} Attack(s) will be played an extra time ({card.name})")


def fx_primal_force(engine, caster, target, card, x_amount=0):
    """Transform all Attacks in your Hand into Giant Rock."""
    attacks = [c for c in caster.hand if c.card_type == CardType.ATTACK and c is not card]
    for c in attacks:
        caster.hand.remove(c)
        rock = make_giant_rock()
        if card.upgraded:
            rock.upgrade()
        caster.add_to_hand(rock, engine.log)
    engine.log.append(
        f"{caster.name} transforms {len(attacks)} Attack(s) in hand into Giant Rock ({card.name})")


def fx_stampede(engine, caster, target, card, x_amount=0):
    """Power: at the end of your turn, 1 random Attack in your Hand is played against a random enemy."""
    def _on_turn_end(engine, player, **kw):
        attacks = [c for c in player.hand if c.card_type == CardType.ATTACK]
        if not attacks:
            return
        chosen = player.rng.choice(attacks)
        victim = engine.random_alive_enemy(player)
        if victim is None:
            return
        engine.auto_play_card(player, chosen, target=victim, source="Stampede")
    if _arm_once(caster, card, "turn_end", _on_turn_end):
        engine.log.append(f"{caster.name} gains Stampede")


def fx_stomp(engine, caster, target, card, x_amount=0):
    dmg_base = card.val("damage")
    for e in engine.enemies_alive():
        dmg = caster.deal_attack_damage(dmg_base)
        e.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def _stomp_cost(card, player):
    """Costs 1 less for each Attack played this turn."""
    base = card.upgrade_cost if (card.upgraded and card.upgrade_cost is not None) else card.cost
    return max(0, base - getattr(player, "attacks_played_this_turn", 0))


def fx_stoke(engine, caster, target, card, x_amount=0):
    """Exhaust your Hand."""
    # Deferred: pools builds its tables OUT of these effects,
    # so importing it at module level would be a cycle.
    from ..pools import CARD_POOL_IRONCLAD
    hand = [c for c in caster.hand if c is not card]
    for c in hand:
        engine.exhaust_card(caster, c)
    count = len(hand)
    for _ in range(count):
        new_card = caster.rng.choice(CARD_POOL_IRONCLAD)()
        if card.upgraded:
            new_card.upgrade()
        caster.add_to_hand(new_card, engine.log)
    engine.log.append(
        f"{caster.name} exhausts {count} card(s) and draws {count} random card(s) ({card.name})")


def fx_unrelenting(engine, caster, target, card, x_amount=0):
    """Deal damage."""
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    caster.next_attack_free = True
    engine.log.append(f"{caster.name}'s next Attack costs 0 ({card.name})")


def fx_vicious(engine, caster, target, card, x_amount=0):
    """Power: whenever you apply Vulnerable, draw N cards."""
    draw = card.val("cards")

    def _on_status_applied(engine, player, status=None, **kw):
        if status is not StatusType.VULNERABLE:
            return
        engine.draw_extra(player, draw)
    if _arm_once(caster, card, "status_applied", _on_status_applied):
        engine.log.append(f"{caster.name} gains Vicious")
