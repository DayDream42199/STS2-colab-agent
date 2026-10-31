from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent
from ..InstantEffects.instant_block import InstantBlock


class Skittish(StatusEffect):
    """Phantasmal Gardener. The first card attack each turn that gets through
    its Block leaves it `amount` Block - once that attack is over, so the
    attack's own later hits are not blocked by it. The game's SkittishPower:
    once per players' turn, the Block a power's own."""

    def __init__(self, source, target, amount):
        super().__init__("skittish")
        self.source = source
        self.target = target
        self.amount = amount
        self.hit = False
        self.used = False

    def on_owner_turn_end(self):
        pass

    def on_event(self, event, context):
        owner = context.source
        if event is GameEvent.ENEMY_TURN_START:
            self.hit = self.used = False
        elif (event is GameEvent.ATTACKED and context.target is owner
              and context.payload.get("amount", 0) > 0
              and context.payload.get("attacker") in context.all_allies):
            self.hit = True
        elif event is GameEvent.CARD_PLAYED and self.hit and not self.used:
            self.hit, self.used = False, True
            return [InstantBlock(source=owner, target=owner, amount=self.amount,
                                 powered=False, card=False)]
        return None


def skittish_for(players, amount):
    """The game's co-op scaling for Skittish: + half again per extra player."""
    return int(amount * (1 + (max(1, players) - 1) * 0.5))
