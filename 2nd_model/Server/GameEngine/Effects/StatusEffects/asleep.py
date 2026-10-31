from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent


class Asleep(StatusEffect):
    """Lagavulin Matriarch. It sleeps `amount` enemy turns, counting one off
    at the end of each, and its Plating is gone before the last one ends.
    Losing HP to a hit wakes it at once: Plating gone, stunned a turn, then
    on with its moves. The game's AsleepPower; a buff.

    Applied before the Plating, so it is heard first at the enemy turn's end
    and the Plating has no Block left to give on the last one."""

    def __init__(self, source, target, amount):
        super().__init__("asleep")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass                       # counted off in on_event, enemy side only

    def on_event(self, event, context):
        owner = context.source
        if (event is GameEvent.HP_LOST and context.target is owner
                and context.payload.get("amount", 0) > 0):
            self._drop_plating(owner)
            owner.remove_status(self.effect_id)
            owner.woken()
        elif event is GameEvent.ENEMY_TURN_END and owner.get_status(self.effect_id) is self:
            if self.amount <= 1:
                self._drop_plating(owner)
            self.amount -= 1
            if self.amount <= 0:
                owner.remove_status(self.effect_id)
        return None

    @staticmethod
    def _drop_plating(owner):
        plating = owner.get_status("plating")
        if plating is not None:
            plating.amount = 0     # it may already be in this event's round
            owner.remove_status("plating")
