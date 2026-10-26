from ._status_effect import StatusEffect
from ...Events.game_event import GameEvent


class Plow(StatusEffect):
    """Ceremonial Beast charging. Once HP lost brings its holder down to
    `amount` or below, the charge breaks: its Strength is gone, it is stunned
    for a turn, and this is removed - the game's PlowPower. A debuff."""

    IS_DEBUFF = True

    def __init__(self, source, target, amount):
        super().__init__("plow")
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
        for strength in ("strength", "strength_this_turn", "strength_loss_this_turn"):
            owner.remove_status(strength)
        owner.remove_status(self.effect_id)
        broken = getattr(owner, "plow_broken", None)
        if broken is not None:
            broken()
        return None
