from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_add_card import InstantAddCard


class HelloWorld(StatusEffect):
    """At the start of your turn, add `amount` random Common cards into your
    Hand, all different (the game's HelloWorldPower, GetDistinctForCombat).
    Before the hand is drawn, so they take room in it (BeforeHandDraw)."""

    def on_owner_turn_end(self):
        pass

    def __init__(self, source, target, amount):
        super().__init__("hello_world")
        self.source = source
        self.target = target
        self.amount = amount

    def on_event(self, event, context):
        from ...Registry.card_registry import generatable_card_ids
        from ...Cards._card_enums import CardClass, CardRarity

        if event is not GameEvent.BEFORE_HAND_DRAW:
            return None
        if context.target is not context.source:
            return None
        pool = generatable_card_ids(
            card_class=CardClass.IRONCLAD, rarity=CardRarity.COMMON,
            solo=context.solo)
        if not pool:
            return None
        picked = context.rngs.card_generation.sample(pool, min(self.amount, len(pool)))
        return [InstantAddCard(
            source=context.source, target=context.source,
            card_id=card_id, pile=InstantAddCard.HAND)
            for card_id in picked]
