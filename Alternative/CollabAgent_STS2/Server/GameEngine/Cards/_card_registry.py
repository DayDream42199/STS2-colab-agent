from .strike import Strike
from .defend import Defend
from .bash import Bash

_CARD_CLASSES = {}

def register_card(card_class):
    card_id = card_class().card_id
    _CARD_CLASSES[card_id] = card_class
    return card_class

def create_card(card_id):
    card_class = _CARD_CLASSES.get(card_id)
    if card_class is None:
        raise KeyError(f"Unknown card id: {card_id}")
    return card_class()

def known_card_ids():
    return sorted(_CARD_CLASSES)

for _card_class in (Strike, Defend, Bash):
    register_card(_card_class)
