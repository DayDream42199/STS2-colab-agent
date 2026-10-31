from ._status_effect import StatusEffect
from ...Cards._card_enums import CardType


class Smoggy(StatusEffect):
    """Living Fog's Advanced Gas. Once its holder has played a Skill this
    turn, no other Skill may be played until the turn is over - by hand or
    by Havoc and the like. For the rest of the fight. The game's SmoggyPower,
    which Smogs every other Skill after one is played and clears them as the
    turn ends. A debuff."""

    IS_DEBUFF = True

    def __init__(self, source, target, amount=1):
        super().__init__("smoggy")
        self.source = source
        self.target = target
        self.amount = 1          # it does not stack (PowerStackType.Single)

    def forbids_play(self, card):
        return (card.card_type is CardType.SKILL
                and self.target.turn_count("skills_played") > 0)

    def on_owner_turn_end(self):
        pass
