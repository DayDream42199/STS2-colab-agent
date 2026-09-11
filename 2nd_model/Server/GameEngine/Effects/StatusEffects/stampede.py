from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_play_card import InstantPlayCard


class Stampede(StatusEffect):
    """At the end of your turn, one random Attack in your Hand is played
    against a random enemy. TURN_END fires before hands are discarded."""

    def __init__(self, source, target, amount):
        super().__init__("stampede")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass

    def on_event(self, event, context):
        from ...Registry.card_registry import create_card
        from ...Cards._card_enums import CardType

        if event is not GameEvent.TURN_END:
            return None
        if context.target is not context.source:
            return None
        attacks = [c for c in context.source.hand
                   if create_card(c).card_type is CardType.ATTACK]
        living = [e for e in context.all_enemies if e.is_alive()]
        if not attacks or not living:
            return None
        return [InstantPlayCard(
            source=context.source, target=context.source,
            card_id=context.rng.choice(attacks),
            from_pile=InstantPlayCard.HAND,
            at=context.rng.choice(living))]
