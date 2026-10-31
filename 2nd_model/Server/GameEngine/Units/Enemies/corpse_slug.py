from ._scripted import ScriptedEnemy, attack, debuff
from ...Effects.StatusEffects.frail import Frail
from ...Effects.StatusEffects.ravenous import Ravenous


class CorpseSlug(ScriptedEnemy):
    """Underdocks, two or three of them (CorpseSlugsWeak, CorpseSlugsNormal).
    Whip Slap 3 x 2, Glomp 8, Goop (2 Frail), round and round - each slug of
    the group starting at a different point of it. Ravenous: when another
    enemy dies, it is stunned a turn and gains 4 Strength."""

    NAME = "Corpse Slug"
    HP_RANGE = (25, 27)
    WHIP_SLAP = 3
    WHIP_SLAP_HITS = 2
    GLOMP = 8
    GOOP_FRAIL = 2
    RAVENOUS = 4

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._cycle = (attack("Whip Slap", self.WHIP_SLAP, hits=self.WHIP_SLAP_HITS),
                       attack("Glomp", self.GLOMP),
                       debuff("Goop", Frail, self.GOOP_FRAIL))
        self.starter = None

    def on_combat_start(self, context):
        return [Ravenous(source=self, target=self, amount=self.RAVENOUS)]

    def pick_move(self, turn):
        if self.starter is None:
            # The game's EnsureCorpseSlugsStartWithDifferentMoves: one random
            # start for the group, then each slug the next one along.
            slugs = [e for e in self.context.all_enemies if isinstance(e, CorpseSlug)]
            first = self.choose_index(3)
            for i, slug in enumerate(slugs):
                if slug.starter is None:
                    slug.starter = (first + i) % 3
        return self._cycle[(self.starter + turn) % len(self._cycle)]
