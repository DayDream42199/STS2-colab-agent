from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_move_card import InstantMoveCard
from ..InstantEffects.instant_upgrade_card import InstantUpgradeCard


class Aggression(StatusEffect):
    """At the start of your turn, take a random Attack out of your Discard Pile
    and upgrade it.

    Upgraded before the move, so the card the player is handed already reads
    the way it will play."""

    def __init__(self, source, target, amount):
        super().__init__("aggression")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # a power, so it lasts the combat

    def on_event(self, event, context):
        from ...Registry.card_registry import create_card
        from ...Cards._card_enums import CardType

        if event is not GameEvent.TURN_START:
            return None
        if context.target is not context.source:
            return None
        ally = context.source
        attacks = [card_id for card_id in ally.discard_pile
                   if create_card(card_id).card_type is CardType.ATTACK]
        if not attacks:
            return None
        chosen = context.rng.choice(attacks)
        return [
            InstantUpgradeCard(source=ally, target=ally, card_refs=[chosen]),
            InstantMoveCard(source=ally, target=ally, card_ids=[chosen],
                            from_pile=InstantMoveCard.DISCARD,
                            to_pile=InstantMoveCard.HAND),
        ]
