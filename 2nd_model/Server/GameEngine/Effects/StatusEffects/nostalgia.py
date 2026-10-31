from ._status_effect import StatusEffect
from ..InstantEffects.instant_move_card import InstantMoveCard


class Nostalgia(StatusEffect):
    """The first `amount` Attacks or Skills you play each turn go on top of
    your Draw Pile instead of to the discard.

    As the game's NostalgiaPower, it counts the Attacks and Skills played this
    turn, not the ones it moved: an Exhausted first Skill still uses it up."""

    def __init__(self, source, target, amount):
        super().__init__("nostalgia")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass

    def redirect_played_card(self, card, context):
        from ...Cards._card_enums import CardType

        if card.card_type not in (CardType.ATTACK, CardType.SKILL):
            return None
        owner = context.source
        # Asked before this play's CARD_PLAYED, so it counts the ones before.
        played = owner.turn_count("attacks_played") + owner.turn_count("skills_played")
        if played >= self.amount:
            return None
        return InstantMoveCard.DRAW
