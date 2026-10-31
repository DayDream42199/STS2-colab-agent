from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent


class Shriek(StatusEffect):
    """Terror Eel. Once HP lost brings its holder down to `amount` or below,
    it is stunned for a turn and this is gone; the move after the stun is
    Terror. The game's ShriekPower. A debuff."""

    IS_DEBUFF = True

    def __init__(self, source, target, amount):
        super().__init__("shriek")
        self.source = source
        self.target = target
        self.amount = amount

    def on_owner_turn_end(self):
        pass

    def on_event(self, event, context):
        owner = context.source
        if (event is not GameEvent.HP_LOST or context.target is not owner
                or owner.current_hp > self.amount):
            return None
        owner.remove_status(self.effect_id)
        broken = getattr(owner, "shriek_broken", None)
        if broken is not None:
            broken()
        return None
