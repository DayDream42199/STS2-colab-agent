class CardRef(str):
    """One physical copy of a card: an id that remembers what happened to it.

    A str subclass, so every id comparison, registry lookup and json dump still
    sees a plain id. What it adds is identity: two Strikes in hand are equal
    but not the same card, so upgrading one leaves the other alone.
    """

    def __new__(cls, card_id, upgraded=False, bonus_damage=0, replay=0,
                cost_bump=0):
        ref = str.__new__(cls, card_id)
        ref.upgraded = upgraded
        ref.bonus_damage = bonus_damage
        ref.replay = replay
        ref.cost_bump = cost_bump
        return ref


def new_ref(card_id):
    """A fresh copy carrying the same state - what "add a copy of this" means."""
    return CardRef(str(card_id), is_upgraded(card_id), bonus_of(card_id),
                   replay_of(card_id), cost_bump_of(card_id))


def is_upgraded(card_id):
    # Bare strings are legal in a pile; they are simply un-upgraded.
    return getattr(card_id, "upgraded", False)


def bonus_of(card_id):
    return getattr(card_id, "bonus_damage", 0)


def replay_of(card_id):
    return getattr(card_id, "replay", 0)


def cost_bump_of(card_id):
    return getattr(card_id, "cost_bump", 0)


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
