class CardRef(str):
    """One physical copy of a card: an id that remembers what happened to it.

    A str subclass, so every id comparison, registry lookup and json dump still
    sees a plain id. What it adds is identity: two Strikes in hand are equal
    but not the same card, so upgrading one leaves the other alone.
    """

    def __new__(cls, card_id, upgraded=False, bonus_damage=0, replay=0,
                cost_bump=0, cost_cap=None, turn_cost_cap=None):
        ref = str.__new__(cls, card_id)
        ref.upgraded = upgraded
        ref.bonus_damage = bonus_damage
        ref.replay = replay
        ref.cost_bump = cost_bump
        # The most this copy costs: for the combat, and for this turn or
        # until it is next played (Enlightenment, and Enlightenment+).
        ref.cost_cap = cost_cap
        ref.turn_cost_cap = turn_cost_cap
        return ref


def new_ref(card_id):
    """A fresh copy carrying the same state - what "add a copy of this" means."""
    return CardRef(str(card_id), is_upgraded(card_id), bonus_of(card_id),
                   replay_of(card_id), cost_bump_of(card_id),
                   getattr(card_id, "cost_cap", None),
                   getattr(card_id, "turn_cost_cap", None))


def is_upgraded(card_id):
    # Bare strings are legal in a pile; they are simply un-upgraded.
    return getattr(card_id, "upgraded", False)


def bonus_of(card_id):
    return getattr(card_id, "bonus_damage", 0)


def replay_of(card_id):
    return getattr(card_id, "replay", 0)


def cost_bump_of(card_id):
    return getattr(card_id, "cost_bump", 0)


def free_copy(card_id, this_combat=False):
    """A new copy of `card_id` that costs 0 this turn or until it is played,
    or with `this_combat` for the rest of the combat - the game's
    SetToFreeThisTurn / SetToFreeThisCombat, on that copy alone. Effects
    that raise a cost (Tangled) still apply on top, and an X card still
    spends what you have, as in the game."""
    ref = new_ref(card_id)
    if this_combat:
        ref.cost_cap = 0
    else:
        ref.turn_cost_cap = 0
    return ref


def cost_cap_of(card_id):
    """The tightest cap on this copy's cost, or None."""
    caps = [cap for cap in (getattr(card_id, "cost_cap", None),
                            getattr(card_id, "turn_cost_cap", None))
            if cap is not None]
    return min(caps) if caps else None


def take(pile, card_id):
    """Remove this exact copy from a pile. True if it was there.

    Identity first: list.remove drops the first EQUAL entry, which with two
    Strikes in hand may be the wrong one.
    """
    for index, held in enumerate(pile):
        if held is card_id:
            del pile[index]
            return True
    if card_id in pile:
        pile.remove(card_id)
        return True
    return False
