from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_block import InstantBlock


class Plating(StatusEffect):
    """At the end of your turn, gain Block equal to your Plating, then lose 1.

    End of turn, not start: the Block has to survive into the enemy phase.

    On an enemy (Sewer Clam) it runs on the enemies' turn, as the game's
    PlatingPower: Block at the end of every enemy turn, and at the start of
    each enemy turn after the first, one less per player in the fight. An
    enemy that arrives with it also starts the fight behind that much Block
    (its on_combat_start gives it). The Block is a power's own, so co-op does
    not scale it again - plating_for scales the Plating instead."""

    def __init__(self, source, target, amount):
        super().__init__("plating")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass  # paid out and counted down together, in on_event

    def on_event(self, event, context):
        owner = context.source
        if owner not in context.all_allies:
            return self._on_enemy(event, context)
        if event is not GameEvent.TURN_END:
            return None
        if context.target is not context.source or self.amount <= 0:
            return None
        block = self.amount
        self.amount -= 1
        return [InstantBlock(powered=False, card=False,
            source=context.source, target=context.source, amount=block)]

    def _on_enemy(self, event, context):
        owner = context.source
        if event is GameEvent.ENEMY_TURN_START and context.counters.get("turn", 1) > 1:
            self.amount -= len(context.all_allies)
        elif event is GameEvent.ENEMY_TURN_END and self.amount > 0:
            return [InstantBlock(powered=False, card=False, source=owner, target=owner,
                                 amount=self.amount)]
        return None


def plating_for(players, amount):
    """The game's co-op scaling for an enemy's Plating: x (2 per extra player + 1)."""
    return amount * ((max(1, players) - 1) * 2 + 1)
