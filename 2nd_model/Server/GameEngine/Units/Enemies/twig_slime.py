from ._scripted import ScriptedEnemy, Move, Branch, attack, hand_out


class TwigSlimeSmall(ScriptedEnemy):
    """Act 1. One move, every turn: Tackle for 4. The smallest thing in the
    Spire - 7 to 11 HP, and the first enemy a single card can kill."""

    NAME = "Twig Slime (S)"
    HP_RANGE = (7, 11)

    TACKLE = 4

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        self._tackle = attack("Tackle", self.TACKLE)

    def pick_move(self, turn):
        return self._tackle


class TwigSlimeMedium(ScriptedEnemy):
    """Act 1. Opens with Sticky Shot (a Slimed to every player), then picks at
    random: Pokey Pounce (11) at most twice running, Sticky Shot never twice
    running - the game's RandomBranchState."""

    NAME = "Twig Slime (M)"
    HP_RANGE = (26, 28)

    POUNCE = 11
    SLIMED = 1

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        sticky = Move("Sticky Shot", Move.DEBUFF, hand_out("slimed", self.SLIMED))
        self._sticky = sticky
        self._branches = (Branch(attack("Pokey Pounce", self.POUNCE), 2),
                          Branch(sticky, Branch.NO_REPEAT))

    def pick_move(self, turn):
        if turn == 0:
            return self._sticky
        return self.choose(self._branches)
