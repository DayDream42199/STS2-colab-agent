# -*- coding: utf-8 -*-
"""Completeness audits for cards, relics and potions -- the same shape as
enemy_audit.py, which caught a whole missing enemy module.

Scope is Ironclad + Colorless only. The other four classes are out of
scope, so their entries are filtered out rather than reported as gaps, and
so are the navigation-tier relics (Shop/Event/Ancient) and gold/shop/rest-
site relics that have no combat-visible effect.
"""
import os
import sys

# The modules under test live one directory up. This used to be a hardcoded
# absolute path, which is why the whole suite only ran on one machine from
# one directory -- and why it lived in a temp folder rather than the repo.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import cards as C
import relics as R
import potions as PT

EXIT = 0


def report(title, wiki_names, have, note=""):
    global EXIT
    wiki = [n for n in wiki_names if n]
    missing = [n for n in wiki if n not in have]
    extra = sorted(n for n in have if n not in wiki)
    print("=" * 74)
    print(title + (f"   ({note})" if note else ""))
    print("=" * 74)
    print(f"  covered: {len(wiki) - len(missing)}/{len(wiki)}")
    if missing:
        print(f"  MISSING ({len(missing)}): {', '.join(sorted(missing))}")
        EXIT = 1
    if extra:
        print(f"  in replica, not on the wiki list ({len(extra)}): {', '.join(extra)}")
    print()


def split(s):
    return [x.strip() for x in s.replace("\n", "|").split("|") if x.strip()]


# ---------------------------------------------------------------------------
# CARDS -- Module:Cards/StS2_data/Ironclad, read three separate times.
# Extraction of this page is demonstrably lossy: read A dropped Bloodletting,
# read B dropped Midnight, read C dropped three more. The union is the only
# defensible denominator, and each individual read is a lower bound.
# ---------------------------------------------------------------------------
IRONCLAD = split("""
Strike|Defend|Bash|
Anger|Armaments|Blood Wall|Bloodletting|Body Slam|Breakthrough|Cinder|Havoc|Headbutt|
Iron Wave|Molten Fist|Perfected Strike|Pommel Strike|Setup Strike|Shrug It Off|
Sword Boomerang|Thunderclap|Tremble|True Grit|Twin Strike|Taunt|
Ashen Strike|Battle Trance|Blaze|Bludgeon|Bully|Burning Pact|Colossus|Cruelty|
Demonic Shield|Dismantle|Drum of Battle|Evil Eye|Expect a Fight|Feel No Pain|Fight Me!|
Flame Barrier|Forgotten Ritual|Grapple|Hemokinesis|Howl from Beyond|Infernal Blade|Inferno|
Inflame|Juggling|Pillage|Rage|Outrage|Rampage|Rupture|Second Wind|Spite|Stampede|Stomp|
Stone Armor|Unrelenting|Uppercut|Vicious|Whirlwind|
Aggression|Barricade|Brand|Cascade|Conflagration|Crimson Mantle|Dark Embrace|Demon Form|
Dominate|Feed|Fiend Fire|Hellraiser|Impervious|Juggernaut|Mangle|Midnight|Not Yet|Offering|
One-Two Punch|Pact's End|Primal Force|Pyre|Stoke|Tank|Tear Asunder|Thrash|Unmovable|
Break|Corruption
""")

have_cards = {c.name for c in (f() for f in C.CARD_POOL_IRONCLAD)}
have_cards |= {c.name for c in (f() for f in C.ANCIENT_CARDS_IRONCLAD)}
have_cards |= {c.name for c in C.make_starter_deck()}
report("IRONCLAD CARDS", IRONCLAD, have_cards,
       "union of 3 independent module reads")

# ---------------------------------------------------------------------------
# COLORLESS -- Module:Cards/StS2_data/Colorless, 151 entries (#39).
# Every one is either ported or on the excluded list below, and the two are
# checked to add up. The old version of this section printed "N of the
# module's 200+ entries", which was both wrong and unverifiable.
# ---------------------------------------------------------------------------
COLORLESS_EXCLUDED = {
    # Quest items: map/event cards with no combat text at all.
    "Byrdonis Egg", "Lantern Key", "Spoils Map", "Dowsing",
    # Other characters' tokens, and Splash ("an Attack from another
    # character"). No class but Ironclad exists here. Sweeping Gaze belongs
    # with them: "Osty deals X damage" is another character's companion.
    "Shiv", "Soul", "Fuel", "Luminesce", "Sovereign Blade",
    "Minion Strike", "Minion Dive Bomb", "Minion Sacrifice",
    "Splash", "Sweeping Gaze",
    # A placeholder whose only text points at the Tinker Time event. Its
    # nine customised printings all have real combat text and ARE ported.
    "Mad Science",
    # NoList duplicate of an already-ported card.
    "Wither (Upgraded)",
}

COLORLESS = set(split("""
Automation|Believe in You|Catastrophe|Coordinate|Dark Shackles|Discovery|
Dramatic Entrance|Equilibrium|Fasten|Finesse|Fisticuffs|Flash of Steel|Gang Up|
Huddle Up|Impatience|Intercept|Jack of All Trades|Lift|Mind Blast|Omnislice|
Panache|Panic Button|Prep Time|Production|Prolong|Prowess|Purity|Restlessness|
Seeker Strike|Shockwave|Splash|Stratagem|Tag Team|The Ball|The Bomb|
Thinking Ahead|Thrumming Hatchet|Ultimate Defend|Ultimate Strike|Volley|
Alchemize|Anointed|Beacon of Hope|Beat Down|Bolas|Calamity|Entropy|
Eternal Armor|Gold Axe|Hand of Greed|Hidden Gem|Jackpot|Knockdown|
Master of Strategy|Mayhem|Mimic|Nostalgia|Rally|Rend|Rolling Boulder|Salvo|
Scrawl|Secret Technique|Secret Weapon|The Gambit|Apotheosis|Apparition|
Brightest Flame|Maul|Neow's Fury|Abundance|Relax|Whistle|Wish|Beckon|Burn|
Dazed|Debris|Disintegration|Frantic Escape|Infection|Mind Rot|Slimed|Sloth|
Soot|Toxic|Void|Waste Away|Wound|Ascender's Bane|Bad Luck|Clumsy|
Curse of the Bell|Debt|Decay|Doubt|Enthralled|Folly|Greed|Guilty|Injury|
Normality|Poor Sleep|Regret|Shame|Spore Mind|Writhe|Byrd Swoop|Enlightenment|
Exterminate|Feeding Frenzy|Metamorphosis|Mad Science|Mad Science (Sapping)|
Mad Science (Violence)|Mad Science (Choking)|Mad Science (Energized)|
Mad Science (Wisdom)|Mad Science (Chaos)|Mad Science (Expertise)|
Mad Science (Improvement)|Mad Science (Curious)|Peck|Squash|Toric Toughness|
Byrdonis Egg|Lantern Key|Spoils Map|Dowsing|Fuel|Giant Rock|Luminesce|
Minion Dive Bomb|Minion Sacrifice|Minion Strike|Shiv|Soul|Sovereign Blade|
Sweeping Gaze|Clash|Dual Wield|Entrench|Caltrops|Distraction|Outmaneuver|
Hello World|Rebound|Rip and Tear|Stack|Wither|Wither (Upgraded)
"""))

have_colorless = {c.name for c in (f() for f in C.COLORLESS_POOL)}
have_colorless |= {c.name for c in (f() for f in C.ANCIENT_COLORLESS)}
have_colorless |= {c.name for c in (f() for f in C.CURSE_POOL)}
have_colorless |= {mk().name for mk in C.STATUS_CARDS}
# Statuses and the one token ported earlier, built by their own make_* fns.
for fn in ("make_wound", "make_infection", "make_dazed", "make_slimed",
           "make_beckon", "make_toxic", "make_burn", "make_frantic_escape",
           "make_giant_rock"):
    have_colorless.add(getattr(C, fn)().name)
have_colorless.add("Wither")

print("=" * 74)
print("COLORLESS CARDS")
print("=" * 74)
if len(COLORLESS) != 151:
    print(f"  !! ledger has {len(COLORLESS)} names, module has 151")
    EXIT = 1
missing = sorted(COLORLESS - have_colorless - COLORLESS_EXCLUDED)
unexpected = sorted(have_colorless - COLORLESS)
print(f"  module entries : {len(COLORLESS)}")
print(f"  ported         : {len(COLORLESS & have_colorless)}")
print(f"  excluded       : {len(COLORLESS_EXCLUDED)}  (quest/other-class/placeholder)")
if missing:
    print(f"  MISSING ({len(missing)}): {', '.join(missing)}")
    EXIT = 1
if unexpected:
    print(f"  NOT IN MODULE ({len(unexpected)}): {', '.join(unexpected)}")
    EXIT = 1
if not missing and not unexpected:
    print("  every module entry is ported or explicitly excluded")
print()

# ---------------------------------------------------------------------------
# RELICS -- Module:Relics/StS2_data defines them directly (no subpages).
# In scope: Common/Uncommon/Rare that are either unclassed or Ironclad.
# Out of scope and filtered: other classes', plus Ancient/Shop/Event tiers,
# plus relics whose only effect is gold/shop/rest-site/map.
# ---------------------------------------------------------------------------
RELICS_COMMON = split("""
Amethyst Aubergine|Anchor|Bag of Marbles|Bag of Preparation|Blood Vial|Book of Five Rings|
Bronze Scales|Centennial Puzzle|Festive Popper|Gorget|Happy Flower|Juzu Bracelet|Lantern|
Meal Ticket|Oddly Smooth Stone|Pendulum|Potion Belt|Red Mask|Regal Pillow|Strawberry|
Strike Dummy|Vajra|Venerable Tea Set|War Paint|Whetstone|Red Skull
""")
RELICS_UNCOMMON = split("""
Akabeko|Bowler Hat|Candelabra|Eternal Feather|Gremlin Horn|Horn Cleat|Joss Paper|Kusarigama|
Lasting Candy|Letter Opener|Lucky Fysh|Mercury Hourglass|Miniature Cannon|Nunchaku|Orichalcum|
Ornamental Fan|Pantograph|Parrying Shield|Pear|Pen Nib|Permafrost|Petrified Toad|Planisphere|
Reptile Trinket|Ripple Basin|Sparkling Rouge|Stone Cracker|Tiny Mailbox|Tuning Fork|Vambrace|
Paper Phrog|Self-Forming Clay
""")
RELICS_RARE = split("""
Art of War|Beating Remnant|Bellows|Captain's Wheel|Chandelier|Cloak Clasp|Frozen Egg|
Gambling Chip|Game Piece|Girya|Ice Cream|Intimidating Helmet|Kunai|Lizard Tail|Mango|
Meat on the Bone|Molten Egg|Mummified Hand|Old Coin|Pocketwatch|Prayer Wheel|Rainbow Ring|
Razor Tooth|Shovel|Shuriken|Stone Calendar|Sturdy Clamp|The Courier|Toxic Egg|Tungsten Rod|
Unceasing Top|Unsettling Lamp|Vexing Puzzlebox|White Beast Statue|White Star|
Charon's Ashes|Demon Tongue|Ruined Helmet
""")
# No combat-visible effect at all -- gold, shops, rest sites, map rooms.
# Verified against each relic's actual Description, not guessed from the
# name. Every one of these has NO combat-visible effect: it pays out in
# gold, at a shop, at a rest site, in a ? room, or in the reward screen.
# Max-HP and heal-at-end-of-combat relics are NOT here - those are combat.
OUT_OF_SCOPE_RELICS = {
    "Amethyst Aubergine",   # "Enemies drop 15 additional Gold."
    "Bowler Hat",           # "Gain 25% additional Gold."
    "Old Coin",             # "Upon pickup, gain 300 Gold."
    "Lucky Fysh",           # "Whenever you add a card to your Deck, gain 15 Gold."
    "Meal Ticket",          # "Whenever you enter a shop room, heal 15 HP."
    "The Courier",          # merchant restocking and prices
    "Juzu Bracelet",        # "Regular enemy combats are no longer encountered in ? rooms."
    "Planisphere",          # "Whenever you enter a ? room, heal 5 HP."
    "Girya",                # "You can now gain Strength at Rest Sites."
    "Shovel",               # "You can now dig at Rest Sites."
    "Eternal Feather",      # heal on entering a Rest Site
    "Regal Pillow",         # "Whenever you Rest, heal an additional 15 HP."
    "Venerable Tea Set",    # bonus energy after a Rest Site
    "Tiny Mailbox",         # "Whenever you Rest, procure 2 random potions."
    "Lasting Candy",        # "your card rewards gain an additional Power"
}
wiki_relics = [n for n in RELICS_COMMON + RELICS_UNCOMMON + RELICS_RARE
               if n not in OUT_OF_SCOPE_RELICS]
have_relics = {r.name for r in R.RELIC_POOL_IRONCLAD} | {R.BURNING_BLOOD.name}
report("RELICS", wiki_relics, have_relics,
       f"{len(OUT_OF_SCOPE_RELICS)} gold/shop/rest-site relics filtered out")

# ---------------------------------------------------------------------------
# POTIONS -- Module:Potions/StS2_data, defined directly. 64 total; the 12
# belonging to the other four classes are out of scope.
# ---------------------------------------------------------------------------
POTIONS = split("""
Attack Potion|Block Potion|Colorless Potion|Dexterity Potion|Energy Potion|Explosive Ampoule|
Fire Potion|Flex Potion|Power Potion|Skill Potion|Speed Potion|Strength Potion|Swift Potion|
Vulnerable Potion|Weak Potion|Blood Potion|
Blessing of the Forge|Clarity Extract|Cure All|Duplicator|Fortifier|Fysh Oil|Gambler's Brew|
Heart of Iron|Liquid Bronze|Potion of Binding|Powdered Demise|Radiant Tincture|Regen Potion|
Stable Serum|Touch of Insanity|Ashwater|
Beetle Juice|Bottled Potential|Distilled Chaos|Droplet of Precognition|Entropic Brew|
Fairy in a Bottle|Fruit Juice|Gigantification Potion|Liquid Memories|Lucky Tonic|
Mazaleth's Gift|Orobic Acid|Shackling Potion|Ship in a Bottle|Snecko Oil|Soldier's Stew|
Ambergris|Foul Potion|Glowwater Potion|Potion-Shaped Rock
""")
have_potions = {p.name for p in PT.POTION_POOL_IRONCLAD} | {p.name for p in PT.SPECIAL_POTIONS}
report("POTIONS", POTIONS, have_potions, "other classes' 12 filtered out")

# ---------------------------------------------------------------------------
# README CLAIMS
#
# content_audit checks the CODE against the wiki; nothing checked the PROSE
# against the code, so README counts went stale silently. Two were found in
# one routine pass: "102 enemies" when enemy_audit had been printing 106/106
# for a while (and two places in the same file disagreed), and "the
# observation is now 202 floats" left over from an earlier task, sitting a
# few hundred lines above a table saying 817.
#
# Claims are marked in the README rather than regexed out of prose:
#     <!--enemies-->106<!--/-->      renders as plain "106"
# because the numbers are not distinguishable by value -- "18" appears there
# as the curse count, an observation size, a benchmark percentage and a
# table cell. A parser that greps bare numbers produces false failures and
# gets switched off. Markers are checked at EVERY occurrence, since the bug
# this exists to catch was two places disagreeing with each other.
# ---------------------------------------------------------------------------
import io
import re
import env as ENV
import enemies as E
import play as PL
from entities import HAND_LIMIT

README = os.path.join(ROOT, "README.md")

LIVE_FACTS = {
    "ironclad_cards":   len(C.CARD_POOL_IRONCLAD) + len(C.ANCIENT_CARDS_IRONCLAD)
                        + len({c.name for c in C.make_starter_deck()}),
    "ironclad_pool":    len(C.CARD_POOL_IRONCLAD),
    "colorless_pool":   len(C.COLORLESS_POOL),
    "ancient_colorless": len(C.ANCIENT_COLORLESS),
    "curses":           len(C.CURSE_POOL),
    "relics":           len(R.RELIC_POOL_IRONCLAD) + 1,      # + Burning Blood
    "potions":          len(PT.POTION_POOL_IRONCLAD) + len(PT.SPECIAL_POTIONS),
    "encounters":       len(PL.ENCOUNTERS),
    "enemies":          106,          # asserted by enemy_audit against the wiki
    "colorless_module": 151,          # the ledger above
    "colorless_ported": None,         # filled in from the ledger below
    "card_ids":         C.TOTAL_CARD_IDS,
    "obs_size":         ENV.OBS_SIZE,
    "action_space":     ENV.END_TURN_ACTION + 1,
    "hand_limit":       HAND_LIMIT,
    "test_suites":      None,         # counted from tests/ below
}
LIVE_FACTS["colorless_ported"] = len(COLORLESS & have_colorless)
LIVE_FACTS["test_suites"] = len([f for f in os.listdir(os.path.dirname(
    os.path.abspath(__file__)))
    if f.endswith(".py") and f not in ("run_all.py",)])

print("=" * 74)
print("README CLAIMS")
print("=" * 74)
if not os.path.exists(README):
    print("  !! README.md not found at " + README)
    EXIT = 1
else:
    text = io.open(README, encoding="utf-8").read()
    claims = re.findall(r"<!--([a-z_]+)-->(\d+)<!--/-->", text)
    seen = {}
    for name, value in claims:
        seen.setdefault(name, []).append(int(value))
    bad, unknown = [], []
    for name, values in sorted(seen.items()):
        live = LIVE_FACTS.get(name)
        if live is None and name not in LIVE_FACTS:
            unknown.append(name)
            continue
        wrong = [v for v in values if v != live]
        if wrong:
            bad.append("{}: README says {} in {} place(s), live value is {}".format(
                name, sorted(set(wrong)), len(wrong), live))
    unmarked = sorted(set(LIVE_FACTS) - set(seen))
    print("  marked claims : {} across {} occurrences".format(len(seen), len(claims)))
    if bad:
        for b in bad:
            print("  STALE: " + b)
        EXIT = 1
    if unknown:
        print("  UNKNOWN marker(s), no live value to check: " + ", ".join(unknown))
        EXIT = 1
    if unmarked:
        # Not a failure: a fact with no marker is simply unclaimed prose.
        print("  (no marker in README, so unchecked: {})".format(", ".join(unmarked)))
    if not bad and not unknown:
        print("  every marked claim matches the live value")
print()

print("=" * 74)
if EXIT:
    print("GAPS FOUND -- see MISSING lines above")
else:
    print("ALL IN-SCOPE CONTENT ACCOUNTED FOR")
sys.exit(EXIT)
