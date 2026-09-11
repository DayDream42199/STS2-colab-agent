"""Status, curse and token cards -- the clutter other things add to your deck."""

from typing import Callable, Dict, List, Optional, Union

from ..statuses import StatusType
from .model import Card, CardType, TargetMode, UNPLAYABLE
from .effects import *  # noqa: F401,F403  -- fx_ names used below
from .effects import _fx_slimed


def make_wound() -> Card:
    """A curse-adjacent Status card, shuffled into a player's discard pile by enemy effects (e.g."""
    return Card("Wound", 999, CardType.STATUS, TargetMode.SELF, lambda *a, **kw: None,
                description="Unplayable.", upgraded_description="Unplayable.")


def make_infection() -> Card:
    """Unplayable (same cost=999 trick as Wound)."""
    return Card("Infection", 999, CardType.STATUS, TargetMode.SELF, lambda *a, **kw: None,
                description="Unplayable. At the end of your turn, if this is in your Hand, take 3 damage.",
                upgraded_description="Unplayable. At the end of your turn, if this is in your Hand, take 3 damage.")


def _status_card(name, text, cost=UNPLAYABLE, effect=None, **kw) -> Card:
    return Card(name, cost, CardType.STATUS, TargetMode.SELF,
                effect or (lambda *a, **kw2: None),
                description=text, upgraded_description=text, **kw)


def make_debris() -> Card:
    return _status_card("Debris", "Exhaust.", cost=1, effect=fx_clear_away, exhausts=True)


def make_disintegration() -> Card:
    """Wiki text is "At the end of your turn, take 6/7/8 damage" -- three numbers on a NoUpgrade card."""
    return _status_card("Disintegration",
                        "Unplayable. At the end of your turn, take 6 damage.")


def make_mind_rot() -> Card:
    return _status_card("Mind Rot", "Unplayable. Draw 1 fewer card each turn.")


def make_sloth() -> Card:
    return _status_card("Sloth", "Unplayable. You cannot play more than 3 cards each turn.")


def make_soot() -> Card:
    return _status_card("Soot", "Unplayable.")


def make_void() -> Card:
    """"Whenever you draw this card, lose 1 Energy." Ethereal, so it clears itself at end of turn..."""
    return _status_card("Void",
                        "Unplayable. Ethereal. Whenever you draw this card, lose 1 Energy.",
                        ethereal=True)


def make_waste_away() -> Card:
    return _status_card("Waste Away", "Unplayable. Gain 1 less Energy per turn.")


STATUS_CARDS = [make_debris, make_disintegration, make_mind_rot, make_sloth,
                make_soot, make_void, make_waste_away]


def _curse(name, text, cost=UNPLAYABLE, effect=None, **kw) -> Card:
    return Card(name, cost, CardType.CURSE, TargetMode.SELF,
                effect or (lambda *a, **kw2: None),
                description=text, upgraded_description=text, **kw)


def make_beckon() -> Card:
    """Soul Fysh's status card: "At the end of your turn, if this is in your Hand, lose 6 HP." Same..."""
    return Card("Beckon", 999, CardType.STATUS, TargetMode.SELF, lambda *a, **kw: None,
                description="Unplayable. At the end of your turn, if this is in your Hand, lose 6 HP.",
                upgraded_description="Unplayable. At the end of your turn, if this is in your Hand, lose 6 HP.")


def make_toxic() -> Card:
    """Myte's status card."""
    return Card("Toxic", 999, CardType.STATUS, TargetMode.SELF, lambda *a, **kw: None,
                description="Unplayable. At the end of your turn, if this is in your Hand, take 5 damage. Exhaust.",
                upgraded_description="Unplayable. At the end of your turn, if this is in your Hand, take 5 damage. Exhaust.")


def make_frantic_escape() -> Card:
    """The Insatiable's status card: "Get farther away."""
    def _fx(engine, caster, target, card, x_amount=0):
        caster.add_status(StatusType.SANDPIT, 1)
        raised = card.current_cost(caster) + 1
        caster.set_temp_cost(card, raised, scope="combat")
        engine.log.append(
            f"{caster.name} scrambles free: Sandpit up to "
            f"{caster.get_status(StatusType.SANDPIT)}, card now costs {raised}")
    return Card("Frantic Escape", 1, CardType.STATUS, TargetMode.SELF, _fx,
                description="Get farther away. Increase Sandpit by 1. Increase the cost of this card by 1.",
                upgraded_description="Get farther away. Increase Sandpit by 1. Increase the cost of this card by 1.")


def make_burn() -> Card:
    """Status card."""
    return Card("Burn", 999, CardType.STATUS, TargetMode.SELF, lambda *a, **kw: None,
                description="Unplayable. At the end of your turn, if this is in your Hand, take 2 damage.",
                upgraded_description="Unplayable. At the end of your turn, if this is in your Hand, take 2 damage.")


def make_wither(bonus: int = 0) -> Card:
    """Aeonglass's status card."""
    dmg = 3 + bonus
    name = "Wither" if bonus == 0 else f"Wither+{bonus}"
    return Card(name, 999, CardType.STATUS, TargetMode.SELF, lambda *a, **kw: None,
                values={"damage": dmg},
                description=f"Unplayable. At the end of your turn, if this is in your Hand, take {dmg} damage.",
                upgraded_description=f"Unplayable. At the end of your turn, if this is in your Hand, take {dmg} damage.")


def make_dazed() -> Card:
    """Unplayable clutter, shuffled in by Haunted Ship's Haunt."""
    return Card("Dazed", 999, CardType.STATUS, TargetMode.SELF, lambda *a, **kw: None,
                description="Unplayable. (Ethereal not modeled -- see make_dazed().)",
                upgraded_description="Unplayable. (Ethereal not modeled -- see make_dazed().)")


def make_slimed() -> Card:
    """Unlike Wound/Infection, real STS Slimed IS playable: costs 1 energy, draws a card, exhausts -- a..."""
    return Card("Slimed", 1, CardType.STATUS, TargetMode.SELF, _fx_slimed,
                exhausts=True,
                description="Draw 1 card. Exhaust.", upgraded_description="Draw 1 card. Exhaust.")
