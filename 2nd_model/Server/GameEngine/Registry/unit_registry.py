from ..Units.Allies.test_ally_1 import TestAlly1
from ..Units.Enemies.dummy_1 import Dummy1
from ..Units.Enemies.the_insatiable import TheInsatiable
from ..Units.Enemies.aeonglass import Aeonglass
from ..Units.Enemies.leaf_slime import LeafSlimeSmall, LeafSlimeMedium
from ..Units.Enemies.twig_slime import TwigSlimeSmall, TwigSlimeMedium
from ..Units.Enemies.wriggler import Wriggler
from ..Units.Enemies.nibbit import Nibbit
from ..Units.Enemies.snapping_jaxfruit import SnappingJaxfruit
from ..Units.Enemies.fuzzy_wurm_crawler import FuzzyWurmCrawler
from ..Units.Enemies.raiders import (AssassinRaider, AxeRaider, BruteRaider, CrossbowRaider,
                                     TrackerRaider)
from ..Units.Enemies.flyconid import Flyconid
from ..Units.Enemies.slithering_strangler import SlitheringStrangler
from ..Units.Enemies.vine_shambler import VineShambler
from ..Units.Enemies.shrinker_beetle import ShrinkerBeetle
from ..Units.Enemies.mawler import Mawler
from ..Units.Enemies.cubex_construct import CubexConstruct

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
# Act 1 (Overgrowth) - type ids are the class names lowercased: leafslimesmall...
for _enemy in (LeafSlimeSmall, LeafSlimeMedium, TwigSlimeSmall, TwigSlimeMedium, Wriggler,
               Nibbit, SnappingJaxfruit, FuzzyWurmCrawler,
               AssassinRaider, AxeRaider, BruteRaider, CrossbowRaider, TrackerRaider,
               Flyconid, SlitheringStrangler, VineShambler, ShrinkerBeetle, Mawler,
               CubexConstruct):
    register_enemy(_enemy)
