from ._instant_effect import InstantEffect


class InstantSummon(InstantEffect):
    """Bring enemies into the fight: Fogmog's Illusory Spores, Phrog Parasite
    dying, a Two-Tailed Rat calling for backup.

    `type_ids` are registry ids; Combat builds them (it owns the rng, the
    scaling and the unit ids), so this is the one effect the Resolver hands
    back to Combat, like InstantPlayCard. `stunned` makes them sit out their
    first enemy phase, as the reference does for backup. The summoner becomes
    their leader: a Minion leaves the fight when its leader dies."""

    def __init__(self, source, type_ids, stunned=False, minion=False):
        super().__init__("instant_summon")
        self.source = source
        self.target = source
        self.type_ids = list(type_ids)
        self.stunned = stunned
        self.minion = minion
