"""Mock card set. Replace with your engine's cards when you plug it in.

`groups` are the Characteristic Analyzer tags from MockUpRB:
  scale / now   -> Scaling
  team  / self  -> Teamwork
Damage and Block are read from the numbers, so attacks don't need a tag.
"""
from dataclasses import dataclass, field
import itertools

TYPES = ("attack", "skill", "power", "status", "curse")
TARGETS = ("single_enemy", "all_enemy", "random_enemy", "self", "single_ally", "all_ally", "none")
KEYWORDS = ("exhaust", "ethereal", "retain", "innate", "unplayable")


@dataclass(frozen=True)
class CardDef:
    name: str
    type: str
    cost: int
    target: str
    damage: int = 0
    hits: int = 1
    block: int = 0
    # statuses applied, per recipient: "self", "target", "all_allies", "all_enemies"
    statuses: dict = field(default_factory=dict)
    keywords: frozenset = frozenset()
    groups: frozenset = frozenset()
    # optional question: ("exhaust_from_hand", min_picks, max_picks, draw_per_pick)
    choice: tuple = None


def _d(name, type_, cost, target, **kw):
    for key in ("keywords", "groups"):
        kw[key] = frozenset(kw.get(key, ()))
    return CardDef(name, type_, cost, target, **kw)


CARDS = {
    "Strike": _d("Strike", "attack", 1, "single_enemy", damage=6, groups={"aggressive", "now"}),
    "Defend": _d("Defend", "skill", 1, "self", block=5, groups={"defensive", "now", "self"}),
    "Bash": _d("Bash", "attack", 2, "single_enemy", damage=8,
               statuses={"target": {"vulnerable": 2}}, groups={"aggressive", "now", "team"}),
    "Inflame": _d("Inflame", "power", 1, "self",
                  statuses={"self": {"strength": 2}}, groups={"scale", "self"}),
    "Cover": _d("Cover", "skill", 1, "single_ally", block=8, groups={"defensive", "now", "team"}),
    "Shared Guard": _d("Shared Guard", "skill", 2, "all_ally", block=5,
                       groups={"defensive", "now", "team"}),
    "Cleave": _d("Cleave", "attack", 1, "all_enemy", damage=7, groups={"aggressive", "now"}),
    "Twin Strike": _d("Twin Strike", "attack", 1, "single_enemy", damage=5, hits=2,
                      groups={"aggressive", "now"}),
    "Rally Cry": _d("Rally Cry", "skill", 1, "all_ally",
                    statuses={"all_allies": {"strength": 1}}, keywords={"exhaust"},
                    groups={"scale", "team"}),
    "Weaken": _d("Weaken", "skill", 1, "single_enemy",
                 statuses={"target": {"weak": 2}}, groups={"now", "team"}),
    "Purge": _d("Purge", "skill", 1, "none", keywords={"exhaust"},
                choice=("exhaust_from_hand", 0, 2, 1), groups={"now", "self"}),
}

STARTER = ["Strike"] * 4 + ["Defend"] * 4 + ["Bash"]
EXTRA_POOL = ["Inflame", "Cover", "Shared Guard", "Cleave", "Twin Strike", "Rally Cry", "Weaken", "Purge"]

_uid = itertools.count()


class Card:
    __slots__ = ("defn", "uid", "upgraded")

    def __init__(self, name, upgraded=False):
        self.defn = CARDS[name]
        self.uid = next(_uid)
        self.upgraded = upgraded

    @property
    def name(self):
        return self.defn.name

    def __repr__(self):
        return f"<{self.name}>"


def make_deck(rng, n_extra=3):
    names = STARTER + list(rng.choice(EXTRA_POOL, size=n_extra, replace=False))
    return [Card(n) for n in names]
