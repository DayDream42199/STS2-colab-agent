from ..Cards.strike import Strike
from ..Cards.defend import Defend
from ..Cards.bash import Bash
from ..Cards.demon_form import DemonForm
from ..Cards.pyre import Pyre
from ..Cards.crimson_mantle import CrimsonMantle
from ..Cards.rupture import Rupture
from ..Cards.inferno import Inferno
from ..Cards.juggernaut import Juggernaut
from ..Cards.dark_embrace import DarkEmbrace
from ..Cards.feel_no_pain import FeelNoPain
from ..Cards.vicious import Vicious
from ..Cards.rage import Rage
from ..Cards.flame_barrier import FlameBarrier
from ..Cards.believe_in_you import BelieveInYou
from ..Cards.blaze import Blaze
from ..Cards.blood_wall import BloodWall
from ..Cards.bloodletting import Bloodletting
from ..Cards.bludgeon import Bludgeon
from ..Cards.body_slam import BodySlam
from ..Cards.break_ import Break
from ..Cards.conflagration import Conflagration
from ..Cards.breakthrough import Breakthrough
from ..Cards.coordinate import Coordinate
from ..Cards.fight_me import FightMe
from ..Cards.hemokinesis import Hemokinesis
from ..Cards.huddle_up import HuddleUp
from ..Cards.iron_wave import IronWave
from ..Cards.inflame import Inflame
from ..Cards.lift import Lift
from ..Cards.mimic import Mimic
from ..Cards.pommel_strike import PommelStrike
from ..Cards.perfected_strike import PerfectedStrike
from ..Cards.setup_strike import SetupStrike
from ..Cards.shrug_it_off import ShrugItOff
from ..Cards.sword_boomerang import SwordBoomerang
from ..Cards.taunt import Taunt
from ..Cards.thunderclap import Thunderclap
from ..Cards.twin_strike import TwinStrike
from ..Cards.uppercut import Uppercut

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


for _card_class in (
    Strike, Defend, Bash,
    DemonForm, Pyre, CrimsonMantle, Rupture, Inferno, Juggernaut, DarkEmbrace, FeelNoPain, Vicious, Rage, FlameBarrier,
    BelieveInYou, Blaze, BloodWall, Bloodletting, Bludgeon,
    BodySlam, Break, Breakthrough, Conflagration, Coordinate,
    FightMe, Hemokinesis, HuddleUp, Inflame, IronWave, Lift, Mimic,
    PerfectedStrike, PommelStrike, SetupStrike, ShrugItOff,
    SwordBoomerang, Taunt, Thunderclap, TwinStrike, Uppercut,
):
    register_card(_card_class)
