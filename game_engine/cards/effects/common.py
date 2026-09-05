"""Helpers shared by the effects, plus the one card an effect builds.

The fx_plain_* family below is what a card gets when its behaviour is
ENTIRELY its numbers. Eighteen effects used to be byte-identical copies of
one of these six -- Strike, Bludgeon, Midnight, Ultimate Strike, Hand of
Greed, Giant Rock, Byrd Swoop and Clash were the same two lines eight times
over. The cards stay distinct because `values` and `upgrade_values` still
differ; only the duplicated code is gone.

A card whose behaviour is anything more than this keeps its own function.
That is the line: shared when the body is identical, separate the moment it
is not.
"""

from typing import Callable, Dict, List, Optional, Union
import copy

from ...entities import HAND_LIMIT
from ...statuses import StatusType, DEBUFF_STATUSES
from ..model import Card, CardType, TargetMode, UNPLAYABLE


def fx_plain_attack(engine, caster, target, card, x_amount=0):
    """Deal damage. Nothing else."""
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)


def fx_plain_block(engine, caster, target, card, x_amount=0):
    """Gain Block. Nothing else.

    NOT the same as fx_defend, which also adds caster.defend_block_bonus --
    Fasten reads "gain additional Block from DEFEND cards", so that bonus
    must not leak onto every blocking Skill.
    """
    gained = caster.gain_block(card.val("block"))
    engine.log.append(f"{caster.name} gains {gained} block ({card.name})")


def fx_plain_energy(engine, caster, target, card, x_amount=0):
    """Gain Energy. Nothing else."""
    caster.energy += card.val("energy")
    engine.log.append(f"{caster.name} gains {card.val('energy')} energy ({card.name})")


def fx_attack_vulnerable(engine, caster, target, card, x_amount=0):
    """Deal damage, then apply Vulnerable."""
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    vuln = card.val("vulnerable")
    target.add_status(StatusType.VULNERABLE, vuln, applier=caster)
    engine.log.append(f"{target.name} gains {vuln} vulnerable ({card.name})")


def fx_attack_then_return(engine, caster, target, card, x_amount=0):
    """Deal damage, then return this card to hand next turn."""
    dmg = caster.deal_attack_damage(card.val("damage"))
    target.take_damage(dmg, log=engine.log, label=card.name, attacker=caster)
    _return_next_turn(engine, caster, card)


def fx_clear_away(engine, caster, target, card, x_amount=0):
    """Playing it does nothing but get rid of it. Debris and Spore Mind."""
    engine.log.append(f"{caster.name} clears away {card.name}")


def _auto_target_for(engine, caster, played):
    """Target for a card being played BY another card (Havoc, Cascade)."""
    if played.target == TargetMode.SINGLE_ENEMY:
        alive = engine.enemies_alive()
        if not alive:
            return False, None
        return True, min(alive, key=lambda e: e.hp)
    if played.target == TargetMode.SELF:
        return True, caster
    if played.target == TargetMode.ALLY:
        return True, engine.other_player(caster)
    return True, None


def _arm_once(player, card, event, callback) -> bool:
    """Register a combat-long listener for THIS card instance exactly once."""
    key = (id(card), event)
    if key in player.armed_card_hooks:
        return False
    player.armed_card_hooks.add(key)
    player.register_hook(event, callback)
    return True


def make_giant_rock() -> Card:
    """Colorless token created by Primal Force. Never in the reward pool."""
    return Card("Giant Rock", 1, CardType.ATTACK, TargetMode.SINGLE_ENEMY,
                 fx_plain_attack, values={"damage": 20},
                 upgrade_values={"damage": 24},
                 description="Deal 20 damage.",
                 upgraded_description="Deal 24 damage.")


def _fresh_free_card(caster, factory):
    """A brand-new card instance, free this turn, safe to mutate."""
    c = factory()
    c.cost = 0
    return c


def _pick(caster, seq):
    return caster.rng.choice(list(seq)) if seq else None


def _sample_distinct(caster, seq, n):
    """Up to n DISTINCT entries, for the "choose 1 of 3" cards."""
    seq = list(seq)
    if len(seq) <= n:
        return seq
    idx = caster.rng.sample(range(len(seq)), n)
    return [seq[i] for i in idx]


def _ally_of(engine, caster):
    """The ally a Multiplayer card acts on, or None when playing solo.

    An ARBITRARY pick -- the first living teammate. Correct only for cards
    whose text names no chooser and no randomness ("another player"). If the
    player picks the target, use the `target` the engine resolved; if the
    card says "random", use _random_ally_of.
    """
    return engine.other_player(caster)


def _random_ally_of(engine, caster):
    """A genuinely random living teammate.

    _ally_of returns the FIRST living one, which is indistinguishable from
    random at 2 players and simply wrong at 3-4 -- The Ball says "give it to
    a random ally" and always handed it to the lowest seat. Drawn from
    caster.rng, which start_combat seeds from the engine seed, so this stays
    reproducible.
    """
    allies = engine.other_players(caster)
    return caster.rng.choice(allies) if allies else None


def _arm_power(caster, card, event, callback, expires_this_turn=False):
    """Register a Power's listener exactly once per card INSTANCE."""
    key = (id(card), event)
    if key in caster.armed_card_hooks:
        return False
    caster.armed_card_hooks.add(key)
    caster.register_hook(event, callback, expires_this_turn)
    return True


def _return_next_turn(engine, caster, card):
    """"At the start of your next turn, return this to your Hand." Queued on the player; play_card..."""
    caster.return_to_hand.append(card)
