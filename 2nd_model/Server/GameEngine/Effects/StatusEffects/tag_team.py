from ._status_effect import StatusEffect


class TagTeam(StatusEffect):
    """Marks an enemy: the next Attack another player plays on it is played an
    extra time. Combat asks `spend`, so the applier gets nothing.

    Each Tag Team is its own mark in the game (TagTeamPower is instanced, and
    knows its applier): two players' marks on one enemy are two, and each is
    set off only by somebody else's Attack. `marks` holds (applier, plays)."""

    IS_DEBUFF = True

    def __init__(self, source, target, amount):
        super().__init__("tag_team")
        self.source = source
        self.target = target
        self.amount = amount
        self.marks = [(source, amount)]

    def absorb(self, other):
        self.marks.extend(other.marks)
        self.amount = sum(plays for _, plays in self.marks)

    def spend(self, attacker):
        """The extra plays `attacker`'s Attack gets; those marks are used up."""
        extra = sum(plays for applier, plays in self.marks if applier is not attacker)
        self.marks = [(applier, plays) for applier, plays in self.marks if applier is attacker]
        self.amount = sum(plays for _, plays in self.marks)
        return extra

    def on_owner_turn_end(self):
        pass  # waits for the teammate's attack, however long that takes
