from ._scripted import ScriptedEnemy, Move, Branch, attack, hand_out


class LeafSlimeSmall(ScriptedEnemy):
    """Act 1. Tackle (3) or Goop (a Slimed into every player's discard),
    picked at random but never the same twice running - so a random opener,
    then alternating, as the game's RandomBranchState makes it."""

    NAME = "Leaf Slime (S)"
    HP_RANGE = (11, 15)

    TACKLE = 3
    SLIMED = 1

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        goop = Move("Goop", Move.DEBUFF, hand_out("slimed", self.SLIMED))
        self._branches = (Branch(attack("Tackle", self.TACKLE), Branch.NO_REPEAT),
                          Branch(goop, Branch.NO_REPEAT))

    def pick_move(self, turn):
        return self.choose(self._branches)


class LeafSlimeMedium(ScriptedEnemy):
    """Act 1. The same rhythm as the small one, twice the Slimed and a
    harder hit: Sticky Shot (2 Slimed), Clump Shot (8)."""

    NAME = "Leaf Slime (M)"
    HP_RANGE = (32, 35)

    CLUMP_SHOT = 8
    SLIMED = 2

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        sticky = Move("Sticky Shot", Move.DEBUFF, hand_out("slimed", self.SLIMED))
        self._cycle = (sticky, attack("Clump Shot", self.CLUMP_SHOT))

    def pick_move(self, turn):
        return self._cycle[turn % len(self._cycle)]
