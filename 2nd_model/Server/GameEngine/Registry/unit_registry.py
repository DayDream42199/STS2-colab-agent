from ..Units.Allies.test_ally_1 import TestAlly1
from ..Units.Allies.ironclad import Ironclad
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
from ..Units.Enemies.inklet import Inklet
from ..Units.Enemies.fogmog import Fogmog, EyeWithTeeth
from ..Units.Enemies.phrog_parasite import PhrogParasite
from ..Units.Enemies.bygone_effigy import BygoneEffigy
from ..Units.Enemies.byrdonis import Byrdonis
from ..Units.Enemies.the_kin import KinPriest, KinFollower
from ..Units.Enemies.vantom import Vantom
from ..Units.Enemies.ceremonial_beast import CeremonialBeast
from ..Units.Enemies.seapunk import Seapunk
from ..Units.Enemies.sewer_clam import SewerClam
from ..Units.Enemies.haunted_ship import HauntedShip
from ..Units.Enemies.sludge_spinner import SludgeSpinner
from ..Units.Enemies.punch_construct import PunchConstruct
from ..Units.Enemies.cultists import CalcifiedCultist, DampCultist
from ..Units.Enemies.toadpole import Toadpole
from ..Units.Enemies.corpse_slug import CorpseSlug
from ..Units.Enemies.fossil_stalker import FossilStalker
from ..Units.Enemies.gremlins import GremlinMerc, SneakyGremlin, FatGremlin
from ..Units.Enemies.terror_eel import TerrorEel
from ..Units.Enemies.skulking_colony import SkulkingColony
from ..Units.Enemies.phantasmal_gardener import PhantasmalGardener
from ..Units.Enemies.living_fog import LivingFog, GasBomb
from ..Units.Enemies.two_tailed_rat import TwoTailedRat
from ..Units.Enemies.lagavulin_matriarch import LagavulinMatriarch
from ..Units.Enemies.soul_fysh import SoulFysh
from ..Units.Enemies.waterfall_giant import WaterfallGiant

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
register_ally(Ironclad)
register_enemy(Dummy1)
register_enemy(TheInsatiable)
register_enemy(Aeonglass)
# Act 1 (Overgrowth) - type ids are the class names lowercased: leafslimesmall...
for _enemy in (LeafSlimeSmall, LeafSlimeMedium, TwigSlimeSmall, TwigSlimeMedium, Wriggler,
               Nibbit, SnappingJaxfruit, FuzzyWurmCrawler,
               AssassinRaider, AxeRaider, BruteRaider, CrossbowRaider, TrackerRaider,
               Flyconid, SlitheringStrangler, VineShambler, ShrinkerBeetle, Mawler,
               CubexConstruct, Inklet, Fogmog, EyeWithTeeth, PhrogParasite, BygoneEffigy,
               Byrdonis, KinPriest, KinFollower, Vantom, CeremonialBeast):
    register_enemy(_enemy)
# Act 1 (Underdocks)
for _enemy in (Seapunk, SewerClam, HauntedShip, SludgeSpinner, PunchConstruct,
               CalcifiedCultist, DampCultist, Toadpole, CorpseSlug, FossilStalker,
               GremlinMerc, SneakyGremlin, FatGremlin, TerrorEel, SkulkingColony,
               PhantasmalGardener, LivingFog, GasBomb, TwoTailedRat,
               LagavulinMatriarch, SoulFysh, WaterfallGiant):
    register_enemy(_enemy)
