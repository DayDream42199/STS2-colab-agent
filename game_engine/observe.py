# -*- coding: utf-8 -*-
"""What a player can see about their teammates, as a small feature vector.

Replaces 3 x 10 x 20 raw ally-hand features with 3 x 12 capability counts.
The slot structure was pure cost there: the action space indexes your OWN
hand, never a teammate's, so nothing addresses those slots.
"""

from .cards import CardType, TargetMode

# Derived from the card pool's own `values` keys, not guessed: damage and
# block dominate, then draw/strength/energy/vulnerable, then a long tail.
# `other` and `dead` exist so no card is invisible -- the same reasoning as
# the `other_debuffs` status channel.
CAPABILITIES = ("damage", "block", "draw", "strength", "energy",
                "vulnerable", "weak", "ally", "other", "dead")
ALLY_FEATURE_NAMES = CAPABILITIES + ("total_damage", "total_block")
ALLY_FEATURES = len(ALLY_FEATURE_NAMES)

_CLUTTER = (CardType.STATUS, CardType.CURSE)


def card_capabilities(card):
    """Which capabilities a single card offers. Never empty."""
    v = card.values
    out = []
    if card.card_type in _CLUTTER:
        return ("dead",)
    if v.get("damage", 0) or v.get("extradamage", 0):
        out.append("damage")
    if v.get("block", 0) or v.get("extrablock", 0):
        out.append("block")
    if v.get("cards", 0) or v.get("draw", 0):
        out.append("draw")
    if v.get("strength", 0):
        out.append("strength")
    if v.get("energy", 0):
        out.append("energy")
    if v.get("vulnerable", 0):
        out.append("vulnerable")
    if v.get("weak", 0):
        out.append("weak")
    if card.target in (TargetMode.ALLY, TargetMode.SELF_OR_ALLY):
        out.append("ally")
    return tuple(out) if out else ("other",)


def summarise_hand(engine, player, max_hand=10):
    """One teammate's hand as ALLY_FEATURES floats, all roughly 0-1.

    Counts what they can PLAY, not what they hold: the hand discards
    wholesale at end of turn, so a card they cannot afford is gone rather
    than waiting. `dead` is the exception and counts held clutter, because
    a clogged hand is exactly the case where holding matters.
    """
    out = [0.0] * ALLY_FEATURES
    if player is None or not player.alive:
        return out
    idx = {name: i for i, name in enumerate(ALLY_FEATURE_NAMES)}
    playable = {id(c) for c in engine.playable_cards(player)}
    for card in player.hand[:max_hand]:
        clutter = card.card_type in _CLUTTER
        if not clutter and id(card) not in playable:
            continue
        for cap in card_capabilities(card):
            out[idx[cap]] += 1.0
        if not clutter:
            out[idx["total_damage"]] += card.val("damage")
            out[idx["total_block"]] += card.val("block")
    for cap in CAPABILITIES:
        out[idx[cap]] /= float(max_hand)
    out[idx["total_damage"]] /= 100.0
    out[idx["total_block"]] /= 100.0
    return out


def party_summary(engine, order, max_allies=3, max_hand=10):
    """`order` is the egocentric player order; row 0 (self) is skipped."""
    flat = []
    mates = list(order)[1:max_allies + 1]
    for i in range(max_allies):
        mate = mates[i] if i < len(mates) else None
        flat.extend(summarise_hand(engine, mate, max_hand))
    return flat
