from .._effect import Effect


class StatusEffect(Effect):
    """Base for persistent effects. Subclasses override whichever hooks
    apply — defaults are all no-ops so a status that doesn't affect damage
    doesn't need to know about damage at all."""

    # Order in which statuses fold over a damage figure: lower runs first.
    # Additive effects must land before multiplicative ones, because Slay the
    # Spire computes (base + Strength) * Weak, not base * Weak + Strength.
    # Without this the result would depend on the order statuses happened to
    # be applied in, which is dict insertion order.
    ADDITIVE = 0
    MULTIPLICATIVE = 10
    DAMAGE_ORDER = MULTIPLICATIVE

    def modify_incoming_damage(self, amount):
        return amount

    def modify_outgoing_damage(self, amount):
        return amount

    def on_owner_turn_end(self):
        """Called once when the unit carrying this status ends its own
        turn. Default: tick down by 1, like most STS debuffs/buffs."""
        self.amount -= 1

    def on_event(self, event, context):
        """React to a GameEvent. Return a list of effects for Combat to
        resolve, or None to ignore it. Default: ignore everything, so a
        status that does not react needs to know nothing about events."""
        return None

    def is_expired(self):
        return self.amount <= 0
