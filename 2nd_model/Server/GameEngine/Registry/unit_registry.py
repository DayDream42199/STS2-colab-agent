from ..Units.Allies.test_ally_1 import TestAlly1
from ..Units.Enemies.dummy_1 import Dummy1
from ..Units.Enemies.the_insatiable import TheInsatiable
from ..Units.Enemies.aeonglass import Aeonglass

_ALLY_CLASSES = {}
_ENEMY_CLASSES = {}


def register_ally(ally_class):
    _ALLY_CLASSES[ally_class.type_id()] = ally_class
    return ally_class


def register_enemy(enemy_class):
    _ENEMY_CLASSES[enemy_class.type_id()] = enemy_class
    return enemy_class


def create_ally(type_id, unit_id, **kwargs):
    ally_class = _ALLY_CLASSES.get(type_id)
    if ally_class is None:
        raise KeyError(f"Unknown ally type id: {type_id}")
    return ally_class(unit_id, **kwargs)


def create_enemy(type_id, unit_id, **kwargs):
    enemy_class = _ENEMY_CLASSES.get(type_id)
    if enemy_class is None:
        raise KeyError(f"Unknown enemy type id: {type_id}")
    return enemy_class(unit_id, **kwargs)


def known_ally_type_ids():
    return sorted(_ALLY_CLASSES)


def known_enemy_type_ids():
    return sorted(_ENEMY_CLASSES)


register_ally(TestAlly1)
register_enemy(Dummy1)
register_enemy(TheInsatiable)
register_enemy(Aeonglass)
