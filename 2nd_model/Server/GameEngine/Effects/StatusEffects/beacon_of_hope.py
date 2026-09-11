from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_block import InstantBlock


class BeaconOfHope(StatusEffect):
    """Whenever the owner gains Block on their own turn, every other living
    ally gains half as much.

    Only the owner's own Block counts, so this cannot feed itself."""

    def __init__(self, source, target, amount):
        super().__init__("beacon_of_hope")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass

    def on_event(self, event, context):
        if event is not GameEvent.BLOCK_GAINED:
            return None
        if context.target is not context.source:
            return None
        if context.payload.get("phase") != "PLAYER_TURN":
            return None
        shared = context.payload.get("amount", 0) // 2
        if shared <= 0:
            return None
        return [
            InstantBlock(source=context.source, target=ally, amount=shared)
            for ally in context.all_allies
            if ally is not context.source and ally.is_alive()
        ]
