"""What each colorless card does."""

from typing import Callable, Dict, List, Optional, Union
import copy

from ...entities import HAND_LIMIT
from ...statuses import StatusType, DEBUFF_STATUSES
from ..model import Card, CardType, TargetMode, UNPLAYABLE
from .common import *  # noqa: F401,F403
from .common import (_ally_of, _random_ally_of, _arm_once, _arm_power,
                     _auto_target_for, _fresh_free_card, _pick,
                     _return_next_turn, _sample_distinct,
                     make_giant_rock)


def fx_finesse(engine, caster, target, card, x_amount=0):
    caster.gain_block(card.val("block"))
    engine.draw_extra(caster, 1)


def fx_flash_of_steel(engine, caster, target, card, x_amount=0):
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    engine.draw_extra(caster, 1)


def fx_dark_shackles(engine, caster, target, card, x_amount=0):
    """Enemy loses N Strength this turn. Exhaust."""
    amount = card.val("strength_loss")
    target.add_status(StatusType.STRENGTH_LOSS_THIS_TURN, amount, applier=caster)
    engine.log.append(f"{target.name} loses {amount} strength this turn ({card.name})")


def fx_prowess(engine, caster, target, card, x_amount=0):
    n = card.val("amount")
    caster.add_status(StatusType.STRENGTH, n)
    caster.add_status(StatusType.DEXTERITY, n)


def fx_impatience(engine, caster, target, card, x_amount=0):
    """If you have no Attacks in your Hand, draw N cards."""
    if any(c.card_type == CardType.ATTACK for c in caster.hand):
        engine.log.append(f"{card.name} fizzles (Attacks in hand)")
        return
    engine.draw_extra(caster, card.val("cards"))


def fx_shockwave(engine, caster, target, card, x_amount=0):
    n = card.val("amount")
    for e in engine.enemies_alive():
        e.add_status(StatusType.WEAK, n, applier=caster)
        e.add_status(StatusType.VULNERABLE, n, applier=caster)
    engine.log.append(f"{caster.name} applies {n} Weak and Vulnerable to all ({card.name})")


def fx_mind_blast(engine, caster, target, card, x_amount=0):
    """Innate. Deal damage equal to the number of cards in your Draw Pile."""
    dmg = caster.deal_attack_damage(len(caster.draw_pile))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_dramatic_entrance(engine, caster, target, card, x_amount=0):
    base = card.val("damage")
    for e in engine.enemies_alive():
        e.take_damage(caster.deal_attack_damage(base), log=engine.log,
                       label=card.name, attacker=caster)


def fx_fisticuffs(engine, caster, target, card, x_amount=0):
    """Deal damage. Gain Block equal to damage dealt."""
    dmg = caster.deal_attack_damage(card.val("damage"))
    result = target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    dealt = result.to_block + result.to_hp
    caster.gain_block(dealt)
    engine.log.append(f"{caster.name} gains block equal to {dealt} damage dealt ({card.name})")


def fx_omnislice(engine, caster, target, card, x_amount=0):
    """Deal damage. Damage ALL other enemies equal to the damage dealt."""
    dmg = caster.deal_attack_damage(card.val("damage"))
    result = target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    dealt = result.to_block + result.to_hp
    for e in engine.enemies_alive():
        if e is not target:
            e.take_damage(dealt, log=engine.log, label=card.name, attacker=caster)


def fx_entrench(engine, caster, target, card, x_amount=0):
    caster.gain_block(caster.block)
    engine.log.append(f"{caster.name} doubles their block to {caster.block} ({card.name})")


def fx_caltrops(engine, caster, target, card, x_amount=0):
    """Power: whenever you are attacked, deal N damage back -- i.e."""
    amount = card.val("thorns")
    caster.add_status(StatusType.THORNS, amount)
    engine.log.append(f"{caster.name} gains {amount} Thorns ({card.name})")


def fx_eternal_armor(engine, caster, target, card, x_amount=0):
    caster.add_status(StatusType.PLATED_ARMOR, card.val("plating"))


def fx_rend(engine, caster, target, card, x_amount=0):
    """Deal damage, plus more for each UNIQUE debuff on the enemy."""
    debuffs = sum(1 for s, v in target.statuses.items()
                  if v > 0 and s in DEBUFF_STATUSES)
    dmg = caster.deal_attack_damage(card.val("damage") + debuffs * card.val("per_debuff"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    engine.log.append(f"{card.name} counted {debuffs} unique debuff(s)")


def fx_master_of_strategy(engine, caster, target, card, x_amount=0):
    engine.draw_extra(caster, card.val("cards"))


def fx_rally(engine, caster, target, card, x_amount=0):
    amount = card.val("block")
    for p in engine.players_alive():
        p.gain_block(amount)
    engine.log.append(f"ALL players gain {amount} block ({card.name})")


def fx_beat_down(engine, caster, target, card, x_amount=0):
    """Play N random Attacks from your Discard Pile."""
    attacks = [c for c in caster.discard_pile if c.card_type == CardType.ATTACK]
    for _ in range(card.val("count")):
        if not attacks:
            break
        chosen = caster.rng.choice(attacks)
        attacks.remove(chosen)
        caster.discard_pile.remove(chosen)
        engine.auto_play_card(caster, chosen, source=card.name)


def fx_catastrophe(engine, caster, target, card, x_amount=0):
    """Play N random cards from your Draw Pile."""
    for _ in range(card.val("count")):
        if not caster.draw_pile:
            break
        chosen = caster.rng.choice(caster.draw_pile)
        caster.draw_pile.remove(chosen)
        engine.auto_play_card(caster, chosen, source=card.name)


def fx_secret_weapon(engine, caster, target, card, x_amount=0):
    """Put an Attack (or Skill) from your Draw Pile into your Hand."""
    want = CardType.ATTACK if card.values.get("want_attack") else CardType.SKILL
    for c in list(caster.draw_pile):
        if c.card_type == want:
            caster.draw_pile.remove(c)
            caster.add_to_hand(c, engine.log)
            engine.log.append(f"{caster.name} pulls {c.name} into hand ({card.name})")
            return
    engine.log.append(f"{card.name} finds nothing to pull")


def fx_automation(engine, caster, target, card, x_amount=0):
    """Power: "Every 10 cards you draw, gain 1 Energy." Counted over the whole combat, not per turn, so..."""
    def on_draw(engine, player, **kw):
        if player.cards_drawn_this_combat % 10 == 0:
            player.energy += 1
            engine.log.append(f"{player.name} gains 1 energy ({card.name})")
    _arm_power(caster, card, "card_drawn", on_draw)


def fx_believe_in_you(engine, caster, target, card, x_amount=0):
    # TargetMode.ALLY: play_card resolved the PLAYER'S choice into `target`.
    # Calling _ally_of instead threw that away and always hit the lowest
    # living seat, which made the action space's ally axis a no-op here.
    ally = target or _ally_of(engine, caster)
    if ally is None:
        engine.log.append(f"{card.name} fizzles: no ally")
        return
    ally.energy += card.val("energy")
    engine.log.append(f"{ally.name} gains {card.val('energy')} energy ({card.name})")


def fx_coordinate(engine, caster, target, card, x_amount=0):
    ally = target or _ally_of(engine, caster)   # honour the chosen ally
    if ally is None:
        engine.log.append(f"{card.name} fizzles: no ally")
        return
    ally.add_status(StatusType.STRENGTH_THIS_TURN, card.val("strength"), applier=caster)
    engine.log.append(f"{ally.name} gains {card.val('strength')} Strength this turn ({card.name})")


def fx_discovery(engine, caster, target, card, x_amount=0):
    """"Choose 1 of 3 random cards to add into your Hand."""
    # Deferred: pools builds its tables OUT of these effects,
    # so importing it at module level would be a cycle.
    from ..pools import CARD_POOL_IRONCLAD
    offer = [_fresh_free_card(caster, f)
             for f in _sample_distinct(caster, CARD_POOL_IRONCLAD, 3)]
    if not offer:
        return
    new_card = engine.request_choice(caster, offer,
                                      "Choose 1 of 3 cards to add to your Hand",
                                      "to_hand")
    caster.add_to_hand(new_card, engine.log)
    engine.log.append(f"{caster.name} adds {new_card.name} (free this turn) to their Hand ({card.name})")


def fx_equilibrium(engine, caster, target, card, x_amount=0):
    gained = caster.gain_block(card.val("block"))
    caster.retain_hand_turns = max(caster.retain_hand_turns, 1)
    engine.log.append(f"{caster.name} gains {gained} block and retains their hand ({card.name})")


def fx_fasten(engine, caster, target, card, x_amount=0):
    caster.defend_block_bonus += card.val("block")
    engine.log.append(f"{caster.name} will gain {caster.defend_block_bonus} extra block from Defend ({card.name})")


def fx_gang_up(engine, caster, target, card, x_amount=0):
    """"Deal 5 damage."""
    others = sum(1 for a in getattr(target, "attacked_by_this_turn", [])
                 if a is not caster)
    dmg = caster.deal_attack_damage(card.val("damage") + others * card.val("bonus"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_huddle_up(engine, caster, target, card, x_amount=0):
    for p in engine.players_alive():
        p.draw_cards(card.val("draw"), engine.log)


def fx_intercept(engine, caster, target, card, x_amount=0):
    caster.gain_block(card.val("block"))
    caster.redirect_attacks_from = [p for p in engine.players_alive() if p is not caster]
    engine.log.append(f"{caster.name} will intercept attacks aimed at allies ({card.name})")


def fx_jack_of_all_trades(engine, caster, target, card, x_amount=0):
    # Deferred: pools builds its tables OUT of these effects,
    # so importing it at module level would be a cycle.
    from ..pools import COLORLESS_POOL
    for _ in range(card.val("count")):
        factory = _pick(caster, COLORLESS_POOL)
        if factory is None:
            break
        caster.add_to_hand(factory(), engine.log)
    engine.log.append(f"{caster.name} adds {card.val('count')} random Colorless card(s) to their Hand")


def fx_lift(engine, caster, target, card, x_amount=0):
    ally = target or _ally_of(engine, caster)   # honour the chosen ally
    if ally is None:
        engine.log.append(f"{card.name} fizzles: no ally")
        return
    gained = ally.gain_block(card.val("block"))
    engine.log.append(f"{ally.name} gains {gained} block ({card.name})")


def fx_panache(engine, caster, target, card, x_amount=0):
    """Power: "Every time you play 5 cards in a single turn, deal X damage to ALL enemies." Fires on..."""
    dmg = card.val("damage")
    def on_play(engine, player, **kw):
        if player.cards_played_this_turn and player.cards_played_this_turn % 5 == 0:
            for e in engine.enemies_alive():
                e.take_damage(player.deal_attack_damage(dmg), log=engine.log,
                               label=card.name, attacker=player)
    _arm_power(caster, card, "card_played", on_play)


def fx_panic_button(engine, caster, target, card, x_amount=0):
    """Block FIRST, then the lockout -- otherwise the card blocks its own Block, which is the obvious..."""
    gained = caster.gain_block(card.val("block"))
    caster.no_card_block_turns = 2
    engine.log.append(f"{caster.name} gains {gained} block but cannot gain block from cards for 2 turns ({card.name})")


def fx_prep_time(engine, caster, target, card, x_amount=0):
    amount = card.val("vigor")
    def on_turn(engine, player, **kw):
        player.add_status(StatusType.VIGOR, amount)
    _arm_power(caster, card, "turn_start", on_turn)


def fx_prolong(engine, caster, target, card, x_amount=0):
    """"Next turn, gain Block equal to your CURRENT Block." Snapshotted now, paid out next turn."""
    snapshot = caster.block
    def payout(player, log):
        gained = player.gain_block(snapshot)
        if log is not None:
            log.append(f"{player.name} gains {gained} block ({card.name})")
    caster.add_delayed_effect(1, "start", payout)
    engine.log.append(f"{caster.name} will gain {snapshot} block next turn ({card.name})")


def fx_purity(engine, caster, target, card, x_amount=0):
    """"Exhaust up to N cards in your Hand." No choice interface, so it exhausts the N cards with the..."""
    remaining = [c for c in caster.hand if c is not card]
    for _ in range(card.val("count")):
        if not remaining:
            break
        chosen = engine.request_choice(caster, remaining,
                                        "Exhaust a card in your Hand", "exhaust")
        remaining = [c for c in remaining if c is not chosen]
        engine.exhaust_card(caster, chosen)


def fx_restlessness(engine, caster, target, card, x_amount=0):
    """"If your Hand is empty, draw N cards and gain M Energy." The card itself has already left hand..."""
    if caster.hand:
        engine.log.append(f"{card.name} does nothing: hand is not empty")
        return
    caster.draw_cards(card.val("draw"), engine.log)
    caster.energy += card.val("energy")


def fx_seeker_strike(engine, caster, target, card, x_amount=0):
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    if caster.draw_pile:
        offer = _sample_distinct(caster, caster.draw_pile, 3)
        picked = engine.request_choice(caster, offer,
                                        "Choose 1 of 3 cards from your Draw Pile",
                                        "to_hand")
        caster.draw_pile.remove(picked)
        caster.add_to_hand(picked, engine.log)
        engine.log.append(f"{caster.name} takes {picked.name} from their draw pile ({card.name})")


def fx_stratagem(engine, caster, target, card, x_amount=0):
    def on_shuffle(engine, player, **kw):
        if player.draw_pile:
            picked = engine.request_choice(player, player.draw_pile,
                                            "Take a card from the reshuffled pile",
                                            "to_hand")
            player.draw_pile.remove(picked)
            player.add_to_hand(picked, engine.log)
            engine.log.append(f"{player.name} takes {picked.name} from the reshuffled pile ({card.name})")
    _arm_power(caster, card, "reshuffle", on_shuffle)


def fx_tag_team(engine, caster, target, card, x_amount=0):
    """"The next Attack another player plays on the enemy is played an extra time." Granted as one..."""
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    ally = _ally_of(engine, caster)
    if ally is not None:
        ally.extra_attack_plays += 1
        engine.log.append(f"{ally.name}'s next Attack is played an extra time ({card.name})")


def fx_the_ball(engine, caster, target, card, x_amount=0):
    """"Increase this card's damage by X this combat and give it to a random ally." combat_bonus_damage..."""
    dmg = caster.deal_attack_damage(card.val("damage") + card.combat_bonus_damage)
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    card.combat_bonus_damage += card.val("bonus")
    # "a RANDOM ally" -- _ally_of would always pick the lowest living seat.
    ally = _random_ally_of(engine, caster)
    if ally is not None:
        ally.discard_pile.append(card)
        engine.log.append(f"{card.name} is passed to {ally.name}")


def fx_the_bomb(engine, caster, target, card, x_amount=0):
    dmg = card.val("damage")
    def boom(player, log):
        for e in engine.enemies_alive():
            e.take_damage(dmg, source_is_attack=False, log=log, label="The Bomb")
    caster.add_delayed_effect(3, "end", boom)
    engine.log.append(f"{caster.name} sets a bomb for {dmg} damage in 3 turns")


def fx_thinking_ahead(engine, caster, target, card, x_amount=0):
    caster.draw_cards(card.val("draw"), engine.log)
    others = [c for c in caster.hand if c is not card]
    if others:
        moved = engine.request_choice(caster, others,
                                       "Put a card on top of your Draw Pile",
                                       "stash")
        caster.hand.remove(moved)
        caster.draw_pile.append(moved)
        engine.log.append(f"{caster.name} puts {moved.name} on top of their draw pile ({card.name})")


def fx_volley(engine, caster, target, card, x_amount=0):
    times = x_amount
    for _ in range(times):
        victim = engine.random_alive_enemy(caster)
        if victim is None:
            break
        victim.take_damage(caster.deal_attack_damage(card.val("damage")),
                            log=engine.log, label=card.name, attacker=caster)


def fx_alchemize(engine, caster, target, card, x_amount=0):
    """"Procure a random potion." Uses the same pool the reward screen does."""
    from ... import potions
    if len(caster.potions) >= caster.potion_slots:
        engine.log.append(f"{caster.name}'s potion belt is full ({card.name})")
        return
    potion = _pick(caster, potions.POTION_POOL_IRONCLAD)
    if potion is None:
        return
    caster.potions.append(potion)
    engine.log.append(f"{caster.name} procures {potion.name} ({card.name})")


def fx_anointed(engine, caster, target, card, x_amount=0):
    rares = [c for c in caster.draw_pile if c.rarity == "Rare"]
    for c in rares:
        caster.draw_pile.remove(c)
        caster.add_to_hand(c, engine.log)
    engine.log.append(f"{caster.name} pulls {len(rares)} Rare card(s) into their Hand ({card.name})")


def fx_beacon_of_hope(engine, caster, target, card, x_amount=0):
    """Power: "Whenever you gain Block on your turn, other players gain half that much Block." Guarded..."""
    caster.share_block_with_allies = True
    def on_block(engine, player, amount=0, **kw):
        if getattr(player, "_beacon_busy", False):
            return
        player._beacon_busy = True
        try:
            for p in engine.players_alive():
                if p is not player:
                    p.gain_block(amount // 2, from_card=False)
        finally:
            player._beacon_busy = False
    _arm_power(caster, card, "block_gained", on_block)


def fx_calamity(engine, caster, target, card, x_amount=0):
    # Deferred: pools builds its tables OUT of these effects,
    # so importing it at module level would be a cycle.
    from ..pools import FACTORIES_BY_TYPE
    def on_attack(engine, player, **kw):
        factories = FACTORIES_BY_TYPE.get(CardType.ATTACK, ())
        if factories:
            player.add_to_hand(_pick(player, factories)(), engine.log)
    _arm_power(caster, card, "attack_played", on_attack)


def fx_entropy(engine, caster, target, card, x_amount=0):
    """Power: "At the start of your turn, Transform 1 card in your Hand."""
    # Deferred: pools builds its tables OUT of these effects,
    # so importing it at module level would be a cycle.
    from ..pools import CARD_POOL_IRONCLAD
    def on_turn(engine, player, **kw):
        if not player.hand:
            return
        old = engine.request_choice(player, player.hand,
                                     "Transform a card in your Hand", "transform")
        player.hand.remove(old)
        new = _pick(player, CARD_POOL_IRONCLAD)()
        player.add_to_hand(new, engine.log)
        engine.log.append(f"{old.name} transforms into {new.name} ({card.name})")
    _arm_power(caster, card, "turn_start", on_turn)


def fx_gold_axe(engine, caster, target, card, x_amount=0):
    dmg = caster.deal_attack_damage(caster.cards_played_this_combat)
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_hidden_gem(engine, caster, target, card, x_amount=0):
    candidates = [c for c in caster.draw_pile if c.replay == 0]
    if not candidates:
        engine.log.append(f"{card.name} finds no card without Replay")
        return
    picked = _pick(caster, candidates)
    caster.grant_replay(picked, card.val("replay"))
    engine.log.append(f"{picked.name} gains {card.val('replay')} Replay ({card.name})")


def fx_jackpot(engine, caster, target, card, x_amount=0):
    # Deferred: pools builds its tables OUT of these effects,
    # so importing it at module level would be a cycle.
    from ..pools import CARD_POOL_IRONCLAD
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    for _ in range(3):
        factory = _pick(caster, CARD_POOL_IRONCLAD)
        if factory is None:
            break
        new_card = _fresh_free_card(caster, factory)
        if card.upgraded:
            new_card.upgrade()
        caster.add_to_hand(new_card, engine.log)


def fx_knockdown(engine, caster, target, card, x_amount=0):
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    target.knockdown = (caster, card.val("mult"))
    engine.log.append(f"{target.name} takes {card.val('mult')}x damage from other players this turn ({card.name})")


def fx_mayhem(engine, caster, target, card, x_amount=0):
    def on_turn(engine, player, **kw):
        if not player.draw_pile:
            return
        top = player.take_top_of_draw(engine.log)
        if top is not None:
            engine.auto_play_card(player, top, source=card.name)
    _arm_power(caster, card, "turn_start", on_turn)


def fx_mimic(engine, caster, target, card, x_amount=0):
    ally = _ally_of(engine, caster)
    if ally is None:
        engine.log.append(f"{card.name} fizzles: no ally")
        return
    gained = caster.gain_block(ally.block)
    engine.log.append(f"{caster.name} mirrors {ally.name}'s block for {gained} ({card.name})")


def fx_nostalgia(engine, caster, target, card, x_amount=0):
    caster.nostalgia = True
    engine.log.append(f"{caster.name}'s first Attack or Skill each turn returns to the draw pile ({card.name})")


def fx_rolling_boulder(engine, caster, target, card, x_amount=0):
    """Power: "At the start of your turn, deal X damage to ALL enemies and increase this damage by 5."..."""
    base = card.val("damage")
    def on_turn(engine, player, **kw):
        amount = base + card.combat_bonus_damage
        for e in engine.enemies_alive():
            e.take_damage(amount, source_is_attack=False, log=engine.log,
                           label=card.name)
        card.combat_bonus_damage += 5
    _arm_power(caster, card, "turn_start", on_turn)


def fx_salvo(engine, caster, target, card, x_amount=0):
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    caster.retain_hand_turns = max(caster.retain_hand_turns, 1)


def fx_scrawl(engine, caster, target, card, x_amount=0):
    """"Draw cards until your Hand is full." Reads the shared HAND_LIMIT, which is now enforced..."""
    need = max(0, HAND_LIMIT - len(caster.hand))
    if need:
        caster.draw_cards(need, engine.log)


def fx_the_gambit(engine, caster, target, card, x_amount=0):
    """"Gain X Block."""
    gained = caster.gain_block(card.val("block"))
    caster.gambit_armed = True
    def on_hp_lost(engine, player, amount=0, source=None, **kw):
        if source == "attack" and amount > 0:
            player.hp = 0
            player.alive = False
            engine.log.append(f"{player.name} loses the gambit and dies ({card.name})")
    _arm_power(caster, card, "hp_lost", on_hp_lost)
    engine.log.append(f"{caster.name} gains {gained} block and will die to any unblocked attack ({card.name})")


def fx_apotheosis(engine, caster, target, card, x_amount=0):
    """"Upgrade ALL your cards." Combat-scoped through upgrade_for_combat, which is reverted at combat..."""
    n = 0
    for pile in (caster.hand, caster.draw_pile, caster.discard_pile):
        for c in pile:
            if not c.upgraded:
                caster.upgrade_for_combat(c)
                n += 1
    engine.log.append(f"{caster.name} upgrades {n} card(s) for this combat ({card.name})")


def fx_apparition(engine, caster, target, card, x_amount=0):
    caster.add_status(StatusType.INTANGIBLE, card.val("intangible"))
    engine.log.append(f"{caster.name} gains {card.val('intangible')} Intangible ({card.name})")


def fx_brightest_flame(engine, caster, target, card, x_amount=0):
    caster.energy += card.val("energy")
    caster.draw_cards(card.val("draw"), engine.log)
    caster.max_hp = max(1, caster.max_hp - 1)
    caster.hp = min(caster.hp, caster.max_hp)
    engine.log.append(f"{caster.name} loses 1 Max HP ({card.name})")


def fx_maul(engine, caster, target, card, x_amount=0):
    """"Deal X damage twice."""
    for _ in range(2):
        if not target.alive:
            break
        dmg = caster.deal_attack_damage(card.val("damage") + card.combat_bonus_damage)
        target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    bonus = card.val("bonus")
    for pile in (caster.hand, caster.draw_pile, caster.discard_pile,
                 caster.exhaust_pile, [card]):
        for c in pile:
            if c.name == "Maul":
                c.combat_bonus_damage += bonus


def fx_neows_fury(engine, caster, target, card, x_amount=0):
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    for _ in range(card.val("count")):
        if not caster.discard_pile:
            break
        picked = engine.request_choice(caster, caster.discard_pile,
                                        "Take a card from your Discard Pile",
                                        "to_hand")
        caster.discard_pile.remove(picked)
        caster.add_to_hand(picked, engine.log)


def fx_abundance(engine, caster, target, card, x_amount=0):
    """"Choose 1 of 3 Powers to add into your Hand." Random pick."""
    # Deferred: pools builds its tables OUT of these effects,
    # so importing it at module level would be a cycle.
    from ..pools import FACTORIES_BY_TYPE
    powers = FACTORIES_BY_TYPE.get(CardType.POWER, ())
    if not powers:
        return
    offer = [_fresh_free_card(caster, f) for f in _sample_distinct(caster, powers, 3)]
    new_card = engine.request_choice(caster, offer,
                                      "Choose 1 of 3 Powers to add to your Hand",
                                      "to_hand")
    caster.add_to_hand(new_card, engine.log)
    engine.log.append(f"{caster.name} adds {new_card.name} (free this turn) to their Hand ({card.name})")


def fx_relax(engine, caster, target, card, x_amount=0):
    caster.gain_block(card.val("block"))
    draw, energy = card.val("draw"), card.val("energy")
    def payout(player, log):
        player.draw_cards(draw, log)
        player.energy += energy
    caster.add_delayed_effect(1, "start", payout)


def fx_whistle(engine, caster, target, card, x_amount=0):
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    if target.alive:
        target.stunned_turns = max(target.stunned_turns, 1)
        engine.log.append(f"{target.name} is stunned ({card.name})")


def fx_wish(engine, caster, target, card, x_amount=0):
    if not caster.draw_pile:
        return
    picked = engine.request_choice(caster, caster.draw_pile,
                                    "Take a card from your Draw Pile", "to_hand")
    caster.draw_pile.remove(picked)
    caster.add_to_hand(picked, engine.log)
    engine.log.append(f"{caster.name} takes {picked.name} from their draw pile ({card.name})")


def fx_enlightenment(engine, caster, target, card, x_amount=0):
    """"Reduce the cost of ALL cards in your Hand to 1 this turn/combat." Routed through set_temp_cost..."""
    scope = "combat" if card.upgraded else "turn"
    for c in caster.hand:
        if c.cost != "X" and c.current_cost(caster) > 1:
            caster.set_temp_cost(c, 1, scope=scope)
    engine.log.append(f"{caster.name}'s hand costs 1 this {scope} ({card.name})")


def fx_exterminate(engine, caster, target, card, x_amount=0):
    for _ in range(4):
        for e in engine.enemies_alive():
            e.take_damage(caster.deal_attack_damage(card.val("damage")),
                           log=engine.log, label=card.name, attacker=caster)


def fx_feeding_frenzy(engine, caster, target, card, x_amount=0):
    caster.add_status(StatusType.STRENGTH_THIS_TURN, card.val("strength"))
    engine.log.append(f"{caster.name} gains {card.val('strength')} Strength this turn ({card.name})")


def fx_metamorphosis(engine, caster, target, card, x_amount=0):
    """"Add N random Attacks into your Draw Pile."""
    # Deferred: pools builds its tables OUT of these effects,
    # so importing it at module level would be a cycle.
    from ..pools import FACTORIES_BY_TYPE
    attacks = FACTORIES_BY_TYPE.get(CardType.ATTACK, ())
    if not attacks:
        return
    for _ in range(card.val("count")):
        new_card = _fresh_free_card(caster, _pick(caster, attacks))
        caster.draw_pile.append(new_card)
    caster.rng.shuffle(caster.draw_pile)
    engine.log.append(f"{caster.name} shuffles {card.val('count')} free Attacks into their draw pile ({card.name})")


def fx_peck_card(engine, caster, target, card, x_amount=0):
    for _ in range(card.val("hits")):
        if not target.alive:
            break
        target.take_damage(caster.deal_attack_damage(card.val("damage")),
                            log=engine.log, label=card.name, attacker=caster)


def fx_squash(engine, caster, target, card, x_amount=0):
    target.take_damage(caster.deal_attack_damage(card.val("damage")),
                        log=engine.log, label=card.name, attacker=caster)
    target.add_status(StatusType.VULNERABLE, card.val("vulnerable"), applier=caster)


def fx_toric_toughness(engine, caster, target, card, x_amount=0):
    amount = card.val("block")
    caster.gain_block(amount)
    def payout(player, log):
        gained = player.gain_block(amount)
        if log is not None:
            log.append(f"{player.name} gains {gained} block ({card.name})")
    caster.add_delayed_effect(1, "start", payout)
    caster.add_delayed_effect(2, "start", payout)


def _clash_playable(card, player):
    """"Can only be played if every card in your Hand is an Attack." Clash itself is still in hand at..."""
    return all(c.card_type == CardType.ATTACK for c in player.hand)


def fx_dual_wield(engine, caster, target, card, x_amount=0):
    """"Choose an Attack or Power card."""
    eligible = [c for c in caster.hand
                if c is not card and c.card_type in (CardType.ATTACK, CardType.POWER)]
    if not eligible:
        engine.log.append(f"{card.name} finds no Attack or Power to copy")
        return
    original = engine.request_choice(caster, eligible,
                                      "Choose an Attack or Power to copy", "copy")
    for _ in range(card.val("copies")):
        caster.add_to_hand(original.clone(), engine.log)
    engine.log.append(f"{caster.name} copies {original.name} x{card.val('copies')} ({card.name})")


def fx_distraction(engine, caster, target, card, x_amount=0):
    # Deferred: pools builds its tables OUT of these effects,
    # so importing it at module level would be a cycle.
    from ..pools import FACTORIES_BY_TYPE
    skills = FACTORIES_BY_TYPE.get(CardType.SKILL, ())
    if not skills:
        return
    new_card = _fresh_free_card(caster, _pick(caster, skills))
    caster.add_to_hand(new_card, engine.log)
    engine.log.append(f"{caster.name} adds {new_card.name} (free this turn) to their Hand ({card.name})")


def fx_outmaneuver(engine, caster, target, card, x_amount=0):
    """"Next turn, gain [@SE@SE|@SE@SE@SE]." VERIFIED (#47): Module:Keywords/StS2_data/Icons defines..."""
    energy = card.val("energy")
    def payout(player, log):
        player.energy += energy
        if log is not None:
            log.append(f"{player.name} gains {energy} energy ({card.name})")
    caster.add_delayed_effect(1, "start", payout)


def fx_hello_world(engine, caster, target, card, x_amount=0):
    # Deferred: pools builds its tables OUT of these effects,
    # so importing it at module level would be a cycle.
    from ..pools import FACTORIES_BY_RARITY
    def on_turn(engine, player, **kw):
        commons = FACTORIES_BY_RARITY.get("Common", ())
        if commons:
            player.add_to_hand(_pick(player, commons)(), engine.log)
    _arm_power(caster, card, "turn_start", on_turn)


def fx_rebound(engine, caster, target, card, x_amount=0):
    target.take_damage(caster.deal_attack_damage(card.val("damage")),
                        log=engine.log, label=card.name, attacker=caster)
    caster.rebound_next_card = card


def fx_rip_and_tear(engine, caster, target, card, x_amount=0):
    for _ in range(2):
        victim = engine.random_alive_enemy(caster)
        if victim is None:
            break
        victim.take_damage(caster.deal_attack_damage(card.val("damage")),
                            log=engine.log, label=card.name, attacker=caster)


def fx_stack(engine, caster, target, card, x_amount=0):
    amount = len(caster.discard_pile) + card.val("bonus")
    gained = caster.gain_block(amount)
    engine.log.append(f"{caster.name} gains {gained} block ({card.name})")


def fx_mad_sapping(engine, caster, target, card, x_amount=0):
    target.take_damage(caster.deal_attack_damage(card.val("damage")),
                        log=engine.log, label=card.name, attacker=caster)
    target.add_status(StatusType.WEAK, 2, applier=caster)
    target.add_status(StatusType.VULNERABLE, 2, applier=caster)


def fx_mad_violence(engine, caster, target, card, x_amount=0):
    for _ in range(3):
        if not target.alive:
            break
        target.take_damage(caster.deal_attack_damage(card.val("damage")),
                            log=engine.log, label=card.name, attacker=caster)


def fx_mad_choking(engine, caster, target, card, x_amount=0):
    """"Whenever you play a card this turn, the enemy loses 6 HP." Turn- scoped, so it uses the..."""
    target.take_damage(caster.deal_attack_damage(card.val("damage")),
                        log=engine.log, label=card.name, attacker=caster)
    victim = target
    def on_play(engine, player, **kw):
        if victim.alive:
            victim.lose_hp(6, log=engine.log, label=card.name)
    caster.register_hook("card_played", on_play, expires_this_turn=True)


def fx_mad_energized(engine, caster, target, card, x_amount=0):
    caster.gain_block(card.val("block"))
    caster.energy += 2


def fx_mad_wisdom(engine, caster, target, card, x_amount=0):
    caster.gain_block(card.val("block"))
    caster.draw_cards(3, engine.log)


def fx_mad_chaos(engine, caster, target, card, x_amount=0):
    # Deferred: pools builds its tables OUT of these effects,
    # so importing it at module level would be a cycle.
    from ..pools import CARD_POOL_IRONCLAD
    caster.gain_block(card.val("block"))
    factory = _pick(caster, CARD_POOL_IRONCLAD)
    if factory is not None:
        caster.add_to_hand(_fresh_free_card(caster, factory), engine.log)


def fx_mad_expertise(engine, caster, target, card, x_amount=0):
    caster.add_status(StatusType.STRENGTH, 2)
    caster.add_status(StatusType.DEXTERITY, 2)


def fx_mad_improvement(engine, caster, target, card, x_amount=0):
    """"At the end of combat, Upgrade a random card." Deck editing between fights is out of scope (no..."""
    candidates = [c for c in caster.draw_pile + caster.hand if not c.upgraded]
    if candidates:
        caster.upgrade_for_combat(_pick(caster, candidates))
        engine.log.append(f"{caster.name} upgrades a card for this combat ({card.name})")


def fx_mad_curious(engine, caster, target, card, x_amount=0):
    """"Powers cost 1 Energy less." Applied to Powers currently in hand and to any drawn later, through..."""
    def discount(c):
        if c.card_type == CardType.POWER and c.cost != "X":
            caster.set_temp_cost(c, max(0, c.current_cost(caster) - 1), scope="combat")
    for c in caster.hand:
        discount(c)
    _arm_power(caster, card, "card_drawn",
               lambda engine, player, card=None, **kw: discount(card))
