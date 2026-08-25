# -*- coding: utf-8 -*-
"""Completeness audit: every enemy named in the wiki's region/Elites/Bosses
data modules, diffed against what the replica actually builds."""
import os
import sys

# The modules under test live one directory up. This used to be a hardcoded
# absolute path, which is why the whole suite only ran on one machine from
# one directory -- and why it lived in a temp folder rather than the repo.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import enemies as E

WIKI = {
"Act 1 / Overgrowth": """Nibbit|Leaf Slime (S)|Leaf Slime (M)|Twig Slime (S)|Twig Slime (M)|
Shrinker Beetle|Fuzzy Wurm Crawler|Inklet|Flyconid|Fogmog|Eye With Teeth|Mawler|
Snapping Jaxfruit|Slithering Strangler|Vine Shambler|Cubex Construct|Axe Raider|
Assassin Raider|Brute Raider|Crossbow Raider|Tracker Raider|Wriggler""",
"Act 1 / Overgrowth elites": "Byrdonis|Bygone Effigy|Phrog Parasite",
"Act 1 / Overgrowth bosses": "Vantom|Ceremonial Beast|Kin Priest|Kin Follower",
"Act 1 / Underdocks": """Corpse Slug|Seapunk|Sludge Spinner|Toadpole|Calcified Cultist|
Damp Cultist|Living Fog|Gas Bomb|Fossil Stalker|Gremlin Merc|Fat Gremlin|Sneaky Gremlin|
Haunted Ship|Punch Construct|Sewer Clam|Two-Tailed Rat""",
"Act 1 / Underdocks elites": "Phantasmal Gardener|Skulking Colony|Terror Eel",
"Act 1 / Underdocks bosses": "Lagavulin Matriarch|Soul Fysh|Waterfall Giant",
"Act 2 / Hive": """Bowlbug (Rock)|Bowlbug (Egg)|Bowlbug (Silk)|Bowlbug (Nectar)|Chomper|
Exoskeleton|Hunter Killer|Louse Progenitor|Mysterious Knight|Myte|Ovicopter|Tough Egg|
Slumbering Beetle|Spiny Toad|The Obscura|Parafright|Thieving Hopper|Tunneler""",
"Act 2 / Hive elites": "Decimillipede|Entomancer|Infested Prism",
"Act 2 / Hive bosses": "The Insatiable|Knowledge Demon|Crusher|Rocket",
"Act 3 / Glory": """Devoted Sculptor|Scroll of Biting|Axebot|Fabricator|Zapbot|Stabbot|
Guardbot|Noisebot|Frog Knight|Globe Head|Owl Magistrate|Slimed Berserker|Living Shield|
Turret Operator|The Lost|The Forgotten""",
"Act 3 / Glory elites": "Mecha Knight|Soul Nexus|Flail Knight|Spectral Knight|Magi Knight",
"Act 3 / Glory bosses": "Doormaker|Queen|Torch Head Amalgam|Test Subject|Aeonglass",
"Event-only enemies": "The Merchant???|Battle Friend V1.0|Battle Friend V2.0|Battle Friend V3.0",
}

have = set()
for n in dir(E):
    if not n.startswith("make_"):
        continue
    try:
        r = getattr(E, n)()
    except Exception:
        continue
    for e in (r if isinstance(r, list) else [r]):
        if isinstance(e, E.Enemy):
            have.add(e.name)

total_w = total_h = 0
missing_all = []
print("=" * 74)
print("ENEMY COVERAGE vs the wiki data modules")
print("=" * 74)
for group, names in WIKI.items():
    wanted = [x.strip() for x in names.replace("\n", "").split("|") if x.strip()]
    missing = [n for n in wanted if n not in have]
    total_w += len(wanted)
    total_h += len(wanted) - len(missing)
    flag = "" if not missing else "   MISSING: " + ", ".join(missing)
    print(f"  {group:<32} {len(wanted)-len(missing):>2}/{len(wanted):<2}{flag}")
    missing_all += missing

all_wiki = {x.strip() for names in WIKI.values()
            for x in names.replace("\n", "").split("|") if x.strip()}
extra = sorted(n for n in have if n not in all_wiki)
print("-" * 74)
print(f"  TOTAL {total_h}/{total_w}")
if extra:
    print(f"  built but not on a wiki module list: {', '.join(extra)}")
print()
if missing_all:
    print(f"INCOMPLETE -- {len(missing_all)} enemy/enemies missing: {missing_all}")
    sys.exit(1)
print("EVERY ENEMY IN ALL THREE ACTS IS PORTED")
