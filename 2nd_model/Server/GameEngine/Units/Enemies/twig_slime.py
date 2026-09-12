from ._scripted import ScriptedEnemy, Move, attack, hand_out


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
    """Act 1. Sticky Shot (1 Slimed), Chomp (11), alternating from the
    Sticky Shot."""

    NAME = "Twig Slime (M)"
    HP_RANGE = (26, 28)

    CHOMP = 11
    SLIMED = 1

    def __init__(self, unit_id, max_hp=None, hp_variance=None, rng=None):
        super().__init__(unit_id, max_hp=max_hp, hp_variance=hp_variance, rng=rng)
        sticky = Move("Sticky Shot", Move.DEBUFF, hand_out("slimed", self.SLIMED),
                      targeted=True)
        self._cycle = (sticky, attack("Chomp", self.CHOMP))

    def pick_move(self, turn):
        return self._cycle[turn % len(self._cycle)]
