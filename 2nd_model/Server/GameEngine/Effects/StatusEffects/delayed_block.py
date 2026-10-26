from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_block import InstantBlock


class DelayedBlock(StatusEffect):
    """Toric Toughness: at the start of each of the next `amount` turns, gain
    again the Block the card gained when it was played.

    As the game's ToricToughnessPower: the Block is what was actually gained
    (after Dexterity and Frail, so 7 for an upgraded card), and gaining it
    again is unpowered and not from a card - Dexterity, Frail and Unmovable
    leave it alone this time. Each play is its own grant (the power is
    Instanced), so two plays give both Blocks, each for its own turns.
    `amount` is the turns left across all grants, which is what is shown."""

    def __init__(self, source, target, amount, block=0):
        super().__init__("delayed_block")
        self.source = source
        self.target = target
        # [Block, turns left] per play.
        self.grants = [[block, amount]]
        self.amount = amount

    def absorb(self, other):
        self.grants.extend(other.grants)
        self.amount = sum(turns for _, turns in self.grants)

    def on_owner_turn_end(self):
        pass  # counted down on use, not on the turn tick

    def on_event(self, event, context):
        if event is not GameEvent.TURN_START:
            return None
        if context.target is not context.source or not self.grants:
            return None
        effects = [InstantBlock(source=context.source, target=context.source,
                                amount=block, powered=False, card=False)
                   for block, _ in self.grants if block > 0]
        for grant in self.grants:
            grant[1] -= 1
        self.grants = [grant for grant in self.grants if grant[1] > 0]
        self.amount = sum(turns for _, turns in self.grants)
        return effects
