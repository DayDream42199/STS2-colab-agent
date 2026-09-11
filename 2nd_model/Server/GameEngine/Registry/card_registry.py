from ..Cards._card_enums import CardClass, CardRarity
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
from ..Cards.ascenders_bane import AscendersBane
from ..Cards.clumsy import Clumsy
from ..Cards.curse_of_the_bell import CurseOfTheBell
from ..Cards.debt import Debt
from ..Cards.folly import Folly
from ..Cards.greed import Greed
from ..Cards.guilty import Guilty
from ..Cards.injury import Injury
from ..Cards.poor_sleep import PoorSleep
from ..Cards.writhe import Writhe
from ..Cards.bad_luck import BadLuck
from ..Cards.decay import Decay
from ..Cards.doubt import Doubt
from ..Cards.shame import Shame
from ..Cards.regret import Regret
from ..Cards.spore_mind import SporeMind
from ..Cards.finesse import Finesse
from ..Cards.flash_of_steel import FlashOfSteel
from ..Cards.master_of_strategy import MasterOfStrategy
from ..Cards.impatience import Impatience
from ..Cards.restlessness import Restlessness
from ..Cards.mind_blast import MindBlast
from ..Cards.equilibrium import Equilibrium
from ..Cards.salvo import Salvo
from ..Cards.headbutt import Headbutt
from ..Cards.neows_fury import NeowsFury
from ..Cards.wish import Wish
from ..Cards.secret_weapon import SecretWeapon
from ..Cards.secret_technique import SecretTechnique
from ..Cards.anointed import Anointed
from ..Cards.ultimate_strike import UltimateStrike
from ..Cards.ultimate_defend import UltimateDefend
from ..Cards.hand_of_greed import HandOfGreed
from ..Cards.production import Production
from ..Cards.dramatic_entrance import DramaticEntrance
from ..Cards.shockwave import Shockwave
from ..Cards.dark_shackles import DarkShackles
from ..Cards.rally import Rally
from ..Cards.beacon_of_hope import BeaconOfHope
from ..Cards.stone_armor import StoneArmor
from ..Cards.eternal_armor import EternalArmor
from ..Cards.prolong import Prolong
from ..Cards.panic_button import PanicButton
from ..Cards.the_gambit import TheGambit
from ..Cards.fasten import Fasten
from ..Cards.prowess import Prowess
from ..Cards.prep_time import PrepTime
from ..Cards.rolling_boulder import RollingBoulder
from ..Cards.the_bomb import TheBomb
from ..Cards.purity import Purity
from ..Cards.primal_force import PrimalForce
from ..Cards.calamity import Calamity
from ..Cards.hello_world import HelloWorld
from ..Cards.entropy import Entropy
from ..Cards.jack_of_all_trades import JackOfAllTrades
from ..Cards.stoke import Stoke
from ..Cards.infernal_blade import InfernalBlade
from ..Cards.distraction import Distraction
from ..Cards.jackpot import Jackpot
from ..Cards.metamorphosis import Metamorphosis
from ..Cards.barricade import Barricade
from ..Cards.whistle import Whistle
from ..Cards.battle_trance import BattleTrance
from ..Cards.pillage import Pillage
from ..Cards.rend import Rend
from ..Cards.scrawl import Scrawl
from ..Cards.havoc import Havoc
from ..Cards.beat_down import BeatDown
from ..Cards.catastrophe import Catastrophe
from ..Cards.howl_from_beyond import HowlFromBeyond
from ..Cards.one_two_punch import OneTwoPunch
from ..Cards.tag_team import TagTeam
from ..Cards.rebound import Rebound
from ..Cards.mayhem import Mayhem
from ..Cards.stampede import Stampede
from ..Cards.hellraiser import Hellraiser
from ..Cards.nostalgia import Nostalgia
from ..Cards.juggling import Juggling
from ..Cards.void import Void
from ..Cards.stomp import Stomp
from ..Cards.midnight import Midnight
from ..Cards.unrelenting import Unrelenting
from ..Cards.corruption import Corruption
from ..Cards.enlightenment import Enlightenment
from ..Cards.whirlwind import Whirlwind
from ..Cards.volley import Volley
from ..Cards.cascade import Cascade
from ..Cards.gold_axe import GoldAxe
from ..Cards.tear_asunder import TearAsunder
from ..Cards.gang_up import GangUp
from ..Cards.fisticuffs import Fisticuffs
from ..Cards.omnislice import Omnislice
from ..Cards.feed import Feed
from ..Cards.ashen_strike import AshenStrike
from ..Cards.pacts_end import PactsEnd
from ..Cards.cinder import Cinder
from ..Cards.true_grit import TrueGrit
from ..Cards.burning_pact import BurningPact
from ..Cards.brand import Brand
from ..Cards.second_wind import SecondWind
from ..Cards.fiend_fire import FiendFire
from ..Cards.drum_of_battle import DrumOfBattle
from ..Cards.spite import Spite
from ..Cards.evil_eye import EvilEye
from ..Cards.colossus import Colossus
from ..Cards.cruelty import Cruelty
from ..Cards.tank import Tank
from ..Cards.knockdown import Knockdown
from ..Cards.panache import Panache
from ..Cards.automation import Automation
from ..Cards.unmovable import Unmovable
from ..Cards.anger import Anger
from ..Cards.outrage import Outrage
from ..Cards.tremble import Tremble
from ..Cards.impervious import Impervious
from ..Cards.forgotten_ritual import ForgottenRitual
from ..Cards.offering import Offering
from ..Cards.bully import Bully
from ..Cards.dismantle import Dismantle
from ..Cards.molten_fist import MoltenFist
from ..Cards.dominate import Dominate
from ..Cards.expect_a_fight import ExpectAFight
from ..Cards.demonic_shield import DemonicShield
from ..Cards.not_yet import NotYet
from ..Cards.mangle import Mangle
from ..Cards.relax import Relax
from ..Cards.apparition import Apparition
from ..Cards.brightest_flame import BrightestFlame
from ..Cards.byrd_swoop import ByrdSwoop
from ..Cards.peck import Peck
from ..Cards.squash import Squash
from ..Cards.exterminate import Exterminate
from ..Cards.rip_and_tear import RipAndTear
from ..Cards.entrench import Entrench
from ..Cards.stack import Stack
from ..Cards.feeding_frenzy import FeedingFrenzy
from ..Cards.caltrops import Caltrops
from ..Cards.toric_toughness import ToricToughness
from ..Cards.outmaneuver import Outmaneuver
from ..Cards.giant_rock import GiantRock
from ..Cards.beckon import Beckon
from ..Cards.burn import Burn
from ..Cards.dazed import Dazed
from ..Cards.debris import Debris
from ..Cards.disintegration import Disintegration
from ..Cards.infection import Infection
from ..Cards.slimed import Slimed
from ..Cards.soot import Soot
from ..Cards.toxic import Toxic
from ..Cards.wither import Wither
from ..Cards.wound import Wound
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
from ..Cards.rampage import Rampage
from ..Cards.maul import Maul
from ..Cards.thrash import Thrash
from ..Cards.bolas import Bolas
from ..Cards.thrumming_hatchet import ThrummingHatchet
from ..Cards.armaments import Armaments
from ..Cards.apotheosis import Apotheosis
from ..Cards.aggression import Aggression
from ..Cards.hidden_gem import HiddenGem
from ..Cards.clash import Clash
from ..Cards.enthralled import Enthralled
from ..Cards.intercept import Intercept
from ..Cards.sloth import Sloth
from ..Cards.normality import Normality
from ..Cards.mind_rot import MindRot
from ..Cards.waste_away import WasteAway
from ..Cards.discovery import Discovery
from ..Cards.abundance import Abundance
from ..Cards.dual_wield import DualWield
from ..Cards.seeker_strike import SeekerStrike
from ..Cards.thinking_ahead import ThinkingAhead
from ..Cards.stratagem import Stratagem
from ..Cards.frantic_escape import FranticEscape
from ..Cards.splash import Splash
from ..Cards.mad_science import VARIANTS as MAD_SCIENCE

_CARD_CLASSES = {}


def register_card(card_class):
    card_id = card_class().card_id
    _CARD_CLASSES[card_id] = card_class
    return card_class


def create_card(card_id):
    """A fresh Card carrying the state of the copy `card_id` names.

    A CardRef looks up the same as the bare id it subclasses, so this is also
    where a copy's upgrade and accumulated damage reach the card.
    """
    card_class = _CARD_CLASSES.get(card_id)
    if card_class is None:
        raise KeyError(f"Unknown card id: {card_id}")
    card = card_class()
    card.bind(card_id)
    return card


def known_card_ids():
    return sorted(_CARD_CLASSES)


# What "a random card" may be: never a starter, an Ancient, or a card you are
# only ever handed (Burn, Wound, a Curse, Giant Rock).
_GENERATABLE_CLASSES = (CardClass.IRONCLAD, CardClass.COLORLESS)
_GENERATABLE_RARITIES = (CardRarity.COMMON, CardRarity.UNCOMMON, CardRarity.RARE)

_generatable_cache = {}


def generatable_card_ids(card_class=None, card_type=None, rarity=None):
    """The card ids that "add a random Attack" and friends may produce.

    Returns ids, not cards - the caller picks with its own rng, so the choice
    stays with the card. Filters are optional and combine.
    """
    key = (card_class, card_type, rarity)
    cached = _generatable_cache.get(key)
    if cached is None:
        cached = tuple(
            card_id for card_id in sorted(_CARD_CLASSES)
            if _is_generatable(create_card(card_id), card_class, card_type, rarity)
        )
        _generatable_cache[key] = cached
    return cached


def _is_generatable(card, card_class, card_type, rarity):
    if card.card_class not in _GENERATABLE_CLASSES:
        return False
    if card.rarity not in _GENERATABLE_RARITIES:
        return False
    if card_class is not None and card.card_class is not card_class:
        return False
    if card_type is not None and card.card_type is not card_type:
        return False
    if rarity is not None and card.rarity is not rarity:
        return False
    return True


for _card_class in (
    Strike, Defend, Bash,
    DemonForm, Pyre, CrimsonMantle, Rupture, Inferno, Juggernaut, DarkEmbrace, FeelNoPain, Vicious, Rage, FlameBarrier,
    AscendersBane, Clumsy, CurseOfTheBell, Debt, Folly, Greed, Guilty, Injury, PoorSleep, Writhe, BadLuck, Decay, Doubt, Shame, Regret, SporeMind,
    Finesse, FlashOfSteel, MasterOfStrategy, Impatience, Restlessness, MindBlast, Equilibrium, Salvo, Headbutt, NeowsFury, Wish, SecretWeapon, SecretTechnique, Anointed,
    UltimateStrike, UltimateDefend, HandOfGreed, Production, DramaticEntrance, Shockwave, DarkShackles, Rally, BeaconOfHope, StoneArmor, EternalArmor, Prolong, PanicButton, TheGambit, Fasten, Prowess, PrepTime, RollingBoulder, TheBomb, Purity, PrimalForce,
    Calamity, HelloWorld, Entropy, JackOfAllTrades, Stoke, InfernalBlade, Distraction, Jackpot, Metamorphosis,
    Barricade, Whistle, BattleTrance, Pillage, Rend, Scrawl,
    Havoc, BeatDown, Catastrophe, HowlFromBeyond, OneTwoPunch, TagTeam, Rebound, Mayhem, Stampede, Hellraiser, Nostalgia, Juggling, Void,
    Stomp, Midnight, Unrelenting, Corruption, Enlightenment, Whirlwind, Volley, Cascade,
    GoldAxe, TearAsunder, GangUp,
    Fisticuffs, Omnislice, Feed,
    AshenStrike, PactsEnd, Cinder, TrueGrit, BurningPact, Brand, SecondWind, FiendFire, DrumOfBattle,
    Spite, EvilEye, Colossus, Cruelty, Tank, Knockdown, Panache, Automation, Unmovable,
    Anger, Outrage, Tremble, Impervious, ForgottenRitual, Offering, Bully, Dismantle, MoltenFist, Dominate, ExpectAFight, DemonicShield, NotYet, Mangle, Relax, Apparition, BrightestFlame,
    ByrdSwoop, Peck, Squash, Exterminate, RipAndTear, Entrench, Stack, FeedingFrenzy, Caltrops, ToricToughness, Outmaneuver,
    GiantRock,
    Beckon, Burn, Dazed, Debris, Disintegration, Infection, Slimed, Soot, Toxic, Wither, Wound,
    BelieveInYou, Blaze, BloodWall, Bloodletting, Bludgeon,
    BodySlam, Break, Breakthrough, Conflagration, Coordinate,
    FightMe, Hemokinesis, HuddleUp, Inflame, IronWave, Lift, Mimic,
    PerfectedStrike, PommelStrike, SetupStrike, ShrugItOff,
    SwordBoomerang, Taunt, Thunderclap, TwinStrike, Uppercut,
    Rampage, Maul, Thrash, Bolas, ThrummingHatchet, Armaments, Apotheosis, Aggression,
    HiddenGem, Clash, Enthralled, Intercept,
    Sloth, Normality, MindRot, WasteAway,
    Discovery, Abundance, DualWield, SeekerStrike, ThinkingAhead, Stratagem,
    FranticEscape, Splash, *MAD_SCIENCE,
):
    register_card(_card_class)
