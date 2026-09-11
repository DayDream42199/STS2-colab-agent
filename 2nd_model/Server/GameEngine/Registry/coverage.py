"""Which cards from the card list are deliberately not in the registry, and why.

Two different reasons, kept apart on purpose:

  EXCLUDED  cannot exist in this game. Nothing in an Ironclad-only co-op run
            can produce them, so porting them would add cards no action can
            ever reach. These are not "later" - they are never.

  DEFERRED  real cards with real values, blocked on a system that does not
            exist yet. The reason names the missing system.
"""

try:
    from .card_registry import known_card_ids
except ImportError:
    # Run directly (python coverage.py) rather than imported as part of the
    # package, so there is no parent to resolve the relative import against.
    # Put Server/ on the path and import by full package name instead.
    import os
    import sys
    sys.path.insert(0, os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..")))
    from GameEngine.Registry.card_registry import known_card_ids


EXCLUDED = {
    # Other characters' tokens. Silent, Regent, Necrobinder and Defect are not
    # ported, so their resource systems (Shivs, Souls/Summon, Star/Forge,
    # Focus/Orbs) do not exist. Verified: no ported card and no enemy move
    # produces any of these.
    "Shiv": "Silent token - Shivs/Poison/Discard not ported",
    "Soul": "Necrobinder token - Souls/Summon/Doom not ported",
    "Minion Strike": "Necrobinder summon token",
    "Minion Dive Bomb": "Necrobinder summon token",
    "Minion Sacrifice": "Necrobinder summon token",
    "Fuel": "other-class token",
    "Luminesce": "other-class token",
    "Sovereign Blade": "other-class token",
    "Sweeping Gaze": "other-class token",

    # Quest items belong to the map/shop layer, which is out of scope: this is
    # a combat replica, and nothing between "combat starts" and "combat ends"
    # can hand you one.
    "Byrdonis Egg": "quest item - map/shop layer not in scope",
    "Dowsing": "quest item - map/shop layer not in scope",
    "Lantern Key": "quest item - map/shop layer not in scope",
    "Spoils Map": "quest item - map/shop layer not in scope",
}


DEFERRED = {
    # Never in scope for a combat replica.
    "Alchemize": "potions - no potion system ported",
}


def coverage(card_list_names):
    """Split a list of card names into ported / excluded / deferred / missing.

    `missing` is the interesting bucket: names that are on the list, are not
    ported, and have no recorded reason - i.e. still to do.
    """
    import re

    from .card_registry import create_card  # noqa: F401

    def key(name):
        # Card lists write "Strike (Ironclad)" and "Wither (Upgraded)"; match on
        # the bare name, ignoring punctuation and spacing entirely.
        name = re.sub(r"\(.*?\)", "", name.lower())
        return re.sub(r"[^a-z0-9]", "", name)

    ported = {key(create_card(cid).name) for cid in known_card_ids()}

    result = {"ported": [], "excluded": [], "deferred": [], "missing": []}
    for name in card_list_names:
        if key(name) in ported:
            result["ported"].append(name)
        elif name in EXCLUDED:
            result["excluded"].append(name)
        elif name in DEFERRED:
            result["deferred"].append(name)
        else:
            result["missing"].append(name)
    return result


if __name__ == "__main__":
    ported = known_card_ids()
    print(f"ported   {len(ported):4}")
    print(f"excluded {len(EXCLUDED):4}  (cannot exist in this game)")
    print(f"deferred {len(DEFERRED):4}  (blocked on a missing system)")

    print()
    print("excluded:")
    for name in sorted(EXCLUDED):
        print(f"   {name:20} {EXCLUDED[name]}")

    print()
    print("deferred, grouped by what is missing:")
    by_reason = {}
    for name, reason in DEFERRED.items():
        by_reason.setdefault(reason, []).append(name)
    for reason in sorted(by_reason):
        print(f"   {reason}")
        for name in sorted(by_reason[reason]):
            print(f"      {name}")
